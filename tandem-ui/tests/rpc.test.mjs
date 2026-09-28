import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { TandemRPC } from "./.generated/rpc.mjs";

class Socket {
  static OPEN = 1;
  static instances = [];
  readyState = 0;
  sent = [];
  constructor(url) { this.url = url; Socket.instances.push(this); }
  send(value) { this.sent.push(JSON.parse(value)); }
  open() { this.readyState = 1; this.onopen?.(); }
  message(value) { this.onmessage?.({ data: JSON.stringify(value) }); }
  close() { this.readyState = 3; this.onclose?.(); }
}
globalThis.WebSocket = Socket;
const clients = [];
afterEach(() => { clients.splice(0).forEach(c => c.disconnect()); Socket.instances = []; });
async function connect(timeout = 1000) {
  const client = new TandemRPC(async () => ({ url: "ws://127.0.0.1:1234", token: "secret" }), timeout);
  clients.push(client);
  await client.connect();
  const socket = Socket.instances.at(-1);
  socket.open();
  return { client, socket };
}
test("authenticates before becoming connected", async () => {
  const { client, socket } = await connect();
  assert.deepEqual(socket.sent, [{ token: "secret" }]);
  assert.equal(client.connected, false);
  await assert.rejects(client.getStatus(), /Not connected/);
  socket.message({ event: "state_snapshot", data: {} });
  assert.equal(client.connected, true);
});
test("resolves matching request and ignores malformed messages", async () => {
  const { client, socket } = await connect();
  socket.message({ event: "state_snapshot", data: {} });
  const result = client.getStatus();
  socket.message(null); socket.message([]);
  socket.message({ id: 1, result: { bonding_active: false } });
  assert.deepEqual(await result, { bonding_active: false });
});
test("missing reply times out and disconnects", async () => {
  const { client, socket } = await connect(20);
  socket.message({ event: "state_snapshot", data: {} });
  await assert.rejects(client.getStatus(), /timed out/);
  assert.equal(client.connected, false);
});
test("disconnect rejects pending work and disables reconnect", async () => {
  const { client, socket } = await connect();
  socket.message({ event: "state_snapshot", data: {} });
  const pending = client.getStatus();
  client.disconnect();
  await assert.rejects(pending, /disconnected/);
  assert.equal(client.connected, false);
});
test("late bootstrap cannot reconnect an unmounted client", async () => {
  let resolve;
  const client = new TandemRPC(() => new Promise(r => { resolve = r; }));
  clients.push(client);
  const pending = client.connect();
  client.disconnect();
  resolve({ url: "ws://127.0.0.1:1", token: "x" });
  await pending;
  assert.equal(Socket.instances.length, 0);
});
