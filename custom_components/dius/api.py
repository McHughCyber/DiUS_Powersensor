"""Async UDP client for DiUS PowerSensor relays."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import json
import logging
import random
import time

from .const import DEFAULT_W_ADJ
from .const import DEFAULT_W_to_U
from .models import CONNECTION_CONNECTING
from .models import CONNECTION_EXPIRED
from .models import CONNECTION_FAILED
from .models import CONNECTION_RECEIVING
from .models import CONNECTION_RECONNECTING
from .models import CONNECTION_STOPPED
from .models import CONNECTION_SUBSCRIBED
from .models import DEFAULT_STALE_TIMEOUT_SECONDS
from .models import DEFAULT_WATCHDOG_TIMEOUT_SECONDS
from .models import ConnectionSnapshot
from .models import DiusDeviceData
from .models import DiusSnapshot
from .models import normalize_instant_power_message

_LOGGER: logging.Logger = logging.getLogger(__package__)

SUBSCRIBE_PAYLOAD = b"subscribe(180)\n"
RESUBSCRIBE_SECONDS = 100
RECONNECT_BACKOFF_INITIAL = 5
RECONNECT_BACKOFF_MAX = 300


class DiusDatagramProtocol(asyncio.DatagramProtocol):
    """UDP protocol that delegates datagrams to the API client."""

    def __init__(self, client: DiusApiClient) -> None:
        """Initialize the protocol."""
        self.client = client

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle an incoming UDP datagram."""
        self.client.receive_datagram(data)

    def error_received(self, exc: Exception) -> None:
        """Handle a UDP transport error."""
        self.client.transport_error(exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle transport closure."""
        if exc is not None:
            self.client.transport_error(exc)


class DiusApiClient:
    """Dius UDP API client."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        u_conv: float = DEFAULT_W_to_U,
        w_adj: float = DEFAULT_W_ADJ,
        stale_timeout_seconds: float = DEFAULT_STALE_TIMEOUT_SECONDS,
        watchdog_timeout_seconds: float = DEFAULT_WATCHDOG_TIMEOUT_SECONDS,
    ) -> None:
        """Initialize the API client."""
        self._host = host
        self._port = port
        self._server_address = (host, port)
        self._u_conv = u_conv
        self._w_adj = w_adj
        self._stale_timeout_seconds = stale_timeout_seconds
        self._watchdog_timeout_seconds = watchdog_timeout_seconds

        self._transport: asyncio.DatagramTransport | None = None
        self._run_task: asyncio.Task | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._reconnect_event = asyncio.Event()
        self._listeners: set[Callable[[], None]] = set()

        self._devices: dict[str, DiusDeviceData] = {}
        self._connection = ConnectionSnapshot(state=CONNECTION_STOPPED)
        self._counters = {
            "messages": 0,
            "parse_errors": 0,
            "invalid_messages": 0,
            "subscription_warnings": 0,
            "subscription_expiries": 0,
            "transport_errors": 0,
        }

    @staticmethod
    async def start(
        host: str,
        port: int,
        *,
        u_conv: float = DEFAULT_W_to_U,
        w_adj: float = DEFAULT_W_ADJ,
        stale_timeout_seconds: float = DEFAULT_STALE_TIMEOUT_SECONDS,
    ) -> DiusApiClient:
        """Create and start a client.

        Kept for backwards compatibility with existing tests and callers.
        """
        client = DiusApiClient(
            host,
            port,
            u_conv=u_conv,
            w_adj=w_adj,
            stale_timeout_seconds=stale_timeout_seconds,
        )
        await client.async_start()
        return client

    async def async_start(self) -> None:
        """Start the UDP client."""
        if self._run_task and not self._run_task.done():
            return
        self._stop_event.clear()
        self._run_task = asyncio.create_task(self._run(), name="dius_udp_client")

    async def async_stop(self) -> None:
        """Stop the UDP client and close transport."""
        self._stop_event.set()
        self._reconnect_event.set()
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._transport:
            self._transport.close()
            self._transport = None
        if self._run_task:
            self._run_task.cancel()
            await asyncio.gather(self._run_task, return_exceptions=True)
        self._set_connection_state(CONNECTION_STOPPED)

    async def stop(self) -> None:
        """Compatibility wrapper for older callers."""
        await self.async_stop()

    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a listener called when the snapshot changes."""
        self._listeners.add(listener)

        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    async def async_get_data(self) -> DiusSnapshot:
        """Return a snapshot of the latest data."""
        return self.snapshot

    @property
    def snapshot(self) -> DiusSnapshot:
        """Return a current snapshot."""
        return DiusSnapshot(
            devices=dict(self._devices),
            connection=self._connection,
            counters=dict(self._counters),
            stale_timeout_seconds=self._stale_timeout_seconds,
        )

    async def async_subscribe(self) -> None:
        """Subscribe to gateway output."""
        if not self._transport:
            raise RuntimeError("UDP transport is not connected")
        self._transport.sendto(SUBSCRIBE_PAYLOAD)
        self._connection = ConnectionSnapshot(
            state=CONNECTION_SUBSCRIBED,
            reconnects=self._connection.reconnects,
            last_message_at=self._connection.last_message_at,
            last_subscribe_at=time.time(),
            last_error=self._connection.last_error,
        )
        self._notify_listeners()

    def receive_datagram(self, data: bytes) -> None:
        """Handle an incoming datagram from the protocol."""
        asyncio.create_task(self.process_message(data))

    def transport_error(self, exc: Exception) -> None:
        """Record transport errors and trigger reconnect."""
        self._counters["transport_errors"] += 1
        self._set_connection_state(CONNECTION_FAILED, str(exc))
        self._reconnect_event.set()

    async def process_message(self, raw_msg: bytes | str) -> None:
        """Process a JSON message."""
        try:
            msg = json.loads(raw_msg)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._counters["parse_errors"] += 1
            self._set_connection_state(CONNECTION_RECEIVING, f"Invalid JSON: {exc}")
            return

        if not isinstance(msg, dict):
            self._counters["invalid_messages"] += 1
            return

        self._counters["messages"] += 1
        now = time.time()
        msg_type = msg.get("type")
        subtype = msg.get("subtype")

        self._connection = ConnectionSnapshot(
            state=CONNECTION_RECEIVING,
            reconnects=self._connection.reconnects,
            last_message_at=now,
            last_subscribe_at=self._connection.last_subscribe_at,
            last_error=None,
        )

        if msg_type == "subscription" and subtype == "warning":
            self._counters["subscription_warnings"] += 1
            _LOGGER.warning("The socket stream had a warning, resubscribing")
            await self.async_subscribe()
            return

        if msg_type == "subscription" and subtype == "expiry":
            self._counters["subscription_expiries"] += 1
            _LOGGER.warning("The socket stream expired, reconnecting")
            self._set_connection_state(CONNECTION_EXPIRED)
            self._reconnect_event.set()
            return

        device = normalize_instant_power_message(
            msg,
            now=now,
            u_conv=self._u_conv,
            w_adj=self._w_adj,
        )
        if device is None:
            self._counters["invalid_messages"] += 1
            self._notify_listeners()
            return

        self._devices[device.key] = device
        self._notify_listeners()

    async def _run(self) -> None:
        """Run the connection loop."""
        backoff = RECONNECT_BACKOFF_INITIAL
        had_failure = False
        while not self._stop_event.is_set():
            try:
                await self._connect()
                if had_failure:
                    self._increment_reconnects()
                had_failure = False
                backoff = RECONNECT_BACKOFF_INITIAL
                await self.async_subscribe()
                self._watchdog_task = asyncio.create_task(self._watchdog())

                wait_tasks = [
                    asyncio.create_task(self._stop_event.wait()),
                    asyncio.create_task(self._reconnect_event.wait()),
                ]
                done, pending = await asyncio.wait(
                    wait_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in done:
                    task.result()
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)

                if self._stop_event.is_set():
                    break
                had_failure = True
                self._reconnect_event.clear()
            except asyncio.CancelledError:
                break
            except Exception as exc:  # pylint: disable=broad-except
                had_failure = True
                self._set_connection_state(CONNECTION_FAILED, str(exc))
                _LOGGER.error(
                    "Unexpected exception in connection to '%s': '%s'",
                    self._host,
                    exc,
                    exc_info=True,
                )
            finally:
                await self._close_transport()

            if not self._stop_event.is_set():
                self._set_connection_state(CONNECTION_RECONNECTING)
                await asyncio.sleep(backoff + random.uniform(0, 1))
                backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX)

    async def _connect(self) -> None:
        """Open the datagram endpoint."""
        self._set_connection_state(CONNECTION_CONNECTING)
        loop = asyncio.get_running_loop()
        transport, _protocol = await loop.create_datagram_endpoint(
            lambda: DiusDatagramProtocol(self),
            remote_addr=self._server_address,
        )
        self._transport = transport

    async def _close_transport(self) -> None:
        """Close the datagram transport."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
            await asyncio.gather(self._watchdog_task, return_exceptions=True)
            self._watchdog_task = None
        if self._transport:
            self._transport.close()
            self._transport = None

    async def _watchdog(self) -> None:
        """Resubscribe periodically and reconnect when data goes stale."""
        while not self._stop_event.is_set():
            await asyncio.sleep(RESUBSCRIBE_SECONDS)
            if not self._transport:
                return
            try:
                await self.async_subscribe()
            except RuntimeError:
                return
            last_message_at = self._connection.last_message_at
            if (
                last_message_at is not None
                and time.time() - last_message_at > self._watchdog_timeout_seconds
            ):
                self._set_connection_state(
                    CONNECTION_EXPIRED,
                    "No messages received before watchdog timeout",
                )
                self._reconnect_event.set()
                return

    def _increment_reconnects(self) -> None:
        """Increment the successful reconnect counter."""
        self._connection = ConnectionSnapshot(
            state=self._connection.state,
            reconnects=self._connection.reconnects + 1,
            last_message_at=self._connection.last_message_at,
            last_subscribe_at=self._connection.last_subscribe_at,
            last_error=self._connection.last_error,
        )

    def _set_connection_state(self, state: str, error: str | None = None) -> None:
        """Set connection state and notify listeners."""
        self._connection = ConnectionSnapshot(
            state=state,
            reconnects=self._connection.reconnects,
            last_message_at=self._connection.last_message_at,
            last_subscribe_at=self._connection.last_subscribe_at,
            last_error=error,
        )
        self._notify_listeners()

    def _notify_listeners(self) -> None:
        """Notify registered listeners."""
        for listener in tuple(self._listeners):
            listener()


async def async_probe_relay(host: str, port: int, timeout: float = 5) -> None:
    """Validate that a UDP relay endpoint can be opened and subscribed to."""
    loop = asyncio.get_running_loop()
    transport = None
    try:
        transport, _protocol = await asyncio.wait_for(
            loop.create_datagram_endpoint(
                lambda: asyncio.DatagramProtocol(),
                remote_addr=(host, port),
            ),
            timeout=timeout,
        )
        transport.sendto(SUBSCRIBE_PAYLOAD)
    finally:
        if transport:
            transport.close()
