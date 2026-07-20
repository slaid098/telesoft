import { API_BASE } from "./api";

export type WsMessage = { type: string; data: unknown };

type MessageHandler = (msg: WsMessage) => void;

const HEARTBEAT_INTERVAL_MS = 25_000;
const HEARTBEAT_TIMEOUT_MS = 30_000;
const RECONNECT_BASE_MS = 1_000;
const RECONNECT_MAX_MS = 30_000;

function buildWsUrl(): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/api/ws`;
}

export class WebSocketClient {
  private url: string;
  private socket: WebSocket | null = null;
  private handlers = new Set<MessageHandler>();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null;
  private manualClose = false;
  private connecting = false;

  constructor(url: string = buildWsUrl()) {
    this.url = url;
  }

  connect(): void {
    if (this.connecting || (this.socket && this.socket.readyState === WebSocket.OPEN)) {
      return;
    }
    this.manualClose = false;
    this.connecting = true;
    const socket = new WebSocket(this.url);
    this.socket = socket;

    socket.onopen = () => {
      this.connecting = false;
      this.reconnectAttempts = 0;
      this.startHeartbeat();
    };

    socket.onmessage = (event: MessageEvent) => {
      this.resetHeartbeatTimeout();
      let payload: WsMessage;
      try {
        payload = JSON.parse(event.data as string) as WsMessage;
      } catch {
        return;
      }
      for (const handler of this.handlers) {
        handler(payload);
      }
    };

    socket.onerror = () => {
      this.connecting = false;
    };

    socket.onclose = () => {
      this.connecting = false;
      this.stopHeartbeat();
      this.socket = null;
      if (!this.manualClose) {
        this.scheduleReconnect();
      }
    };
  }

  onMessage(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => {
      this.handlers.delete(handler);
    };
  }

  send(payload: unknown): boolean {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return false;
    }
    this.socket.send(JSON.stringify(payload));
    return true;
  }

  close(): void {
    this.manualClose = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    const delay = Math.min(RECONNECT_BASE_MS * 2 ** this.reconnectAttempts, RECONNECT_MAX_MS);
    this.reconnectAttempts += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
      this.socket.send(JSON.stringify({ type: "ping" }));
      this.heartbeatTimeoutTimer = setTimeout(() => {
        this.socket?.close();
      }, HEARTBEAT_TIMEOUT_MS);
    }, HEARTBEAT_INTERVAL_MS);
    this.resetHeartbeatTimeout();
  }

  private resetHeartbeatTimeout(): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.resetHeartbeatTimeout();
  }
}
