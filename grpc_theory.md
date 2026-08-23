# gRPC — Theoretical Document
### IT Blackout — MicroClub | Yacine Ould Braham

---

## 1. Introduction — What Is gRPC?

**gRPC** (*Google Remote Procedure Call*) is a client/server communication framework, open-sourced by Google in 2015, designed specifically for distributed systems and microservices architectures.

It is built on the concept of **RPC (Remote Procedure Call)**: calling a function that executes on a remote machine, while giving the developer the illusion of a local function call.

```python
# What the developer writes
order = payment_stub.ProcessPayment(request)

# What actually happens behind this line:
# serialization → network transmission → remote execution → response → deserialization
```

**Historical context:** gRPC is the public version of an internal Google system, **Stubby**, used internally since the early 2000s to connect thousands of services with each other. gRPC carries the same principles forward, built around two technologies: **Protocol Buffers** and **HTTP/2**.

**Key point:** this abstraction ("remote call = local call") is powerful, but dangerous if forgotten. A local call never times out and never fails because of the network. A remote call can — which is exactly why mechanisms like deadlines exist (covered in section 6).

---

## 2. The Contract: Protocol Buffers and the `.proto` File

### 2.1 The problem it solves

Before a client and a server can communicate, they must agree, **in advance**, on:
- Which functions are available
- What parameters they expect
- What type of data they return

This contract is written in a `.proto` file, using the description language specific to **Protocol Buffers**.

### 2.2 Concrete example (from the project)

```protobuf
syntax = "proto3";

message Order {
  string order_id = 1;
  string user_id = 2;
  double amount = 3;
  string status = 4;
}

message OrderRequest {
  string order_id = 1;
}

service OrderService {
  rpc GetOrder(OrderRequest) returns (Order);
  rpc WatchOrderStatus(OrderRequest) returns (stream Order);
}
```

### 2.3 Essential technical points

- **The numbers (`= 1`, `= 2`...)** are not default values: they are the field positions used in binary encoding. They are never renumbered once in production, since doing so would break compatibility with existing clients.
- **Protobuf ≠ `.proto`**: Protobuf is the overall technology (description language + binary format + `protoc` compiler). The `.proto` file is the concrete instance of the contract written with that tool.
- **A Protobuf message is not an ordinary Python class**: it is language-independent (the same `.proto` generates Python, Go, Java code...), each field has a position number, and the generated code natively knows how to serialize/deserialize to and from binary.

### 2.4 From `.proto` to executable code

The `protoc` compiler (provided by `grpcio-tools`) transforms the `.proto` file into **regular Python source code** — not directly into binary. This generated Python code contains classes that, in turn, know how to convert themselves into bytes **at the moment of network transmission**, not before.

```bash
python -m grpc_tools.protoc -I proto --python_out=generated --grpc_python_out=generated proto/order.proto
```

Generates:
- `order_pb2.py` — the message classes (`Order`, `OrderRequest`...)
- `order_pb2_grpc.py` — the stubs and service classes

---

## 3. The Transport: HTTP/2

### 3.1 The problem with HTTP/1.1

In HTTP/1.1, requests are processed one at a time on a single TCP connection (*Head-of-Line Blocking*): if one request is slow, the following ones must wait. Browsers worked around this by opening multiple parallel TCP connections (typically capped at 6 per domain) — a costly and limited solution.

### 3.2 The solution: multiplexing

HTTP/2 allows multiple requests/responses to travel **in parallel over a single TCP connection**, without blocking one another. Each message is split into **frames**, each tagged with a **Stream ID** that identifies it. Frames from different requests are interleaved on the connection, and each request is reassembled as soon as all of its frames have arrived — independently of the others.

This mechanism is what makes gRPC's bidirectional streaming possible, which is physically impossible under HTTP/1.1.

### 3.3 A fundamental distinction — never confuse the two

| | Role | Answers |
|---|---|---|
| **HTTP/2** | Transport | *How* bytes travel (multiplexing, frames, streams) |
| **Protobuf** | Serialization | *What* the bytes mean once they arrive (structure, types) |

Multiplexing does not "condense" or turn anything into binary — it organizes the **transport** of data already serialized by Protobuf. These are two independent layers working together.

---

## 4. The Stub: the Invisible Intermediary

The **stub** is client-side code generated (by `protoc`) that creates the illusion of a local function call. Each stub method corresponds to an `rpc` defined in the `.proto` file.

**What a call like `stub.GetOrder(request)` actually does:**

1. Serializes `request` into Protobuf bytes
2. Sends it over an HTTP/2 connection (framing, multiplexing)
3. Waits for and receives the response
4. Deserializes it back into a Python object (`Order`)
5. Returns that object to the calling code

On the server side, the equivalent is called a **Servicer** — a base class the developer implements to write the actual business logic (e.g. `OrderServiceServicer`).

---

## 5. The 4 Communication Modes

gRPC offers 4 ways to exchange messages, all built on HTTP/2 multiplexing:

| Mode | Description | Example in the project |
|---|---|---|
| **Unary** | 1 request, 1 response | `GetOrder`, `CreateOrder` |
| **Server streaming** | 1 request, multiple responses over time | `WatchOrderStatus` |
| **Client streaming** | Multiple requests, 1 final response | — |
| **Bidirectional streaming** | Both sides stream independently | — |

**The principle behind streaming:** the call stays open, and multiple messages travel over it over time — instead of a single fixed round trip. In `WatchOrderStatus`, the client sends a single initial request; it's the **server** that sends a new message every time it detects a status change on its side.

---

## 6. Deadlines and Propagation

### 6.1 The problem

A network call can fail silently or never respond at all — unlike a local function call. Without explicit handling, client code can block indefinitely while waiting for a response.

### 6.2 The mechanism

A **deadline** is an explicit time limit set by the client on a gRPC call. This information travels in the request's **metadata** (similar to HTTP headers).

**Propagation across a chain:** if Service A calls B with a 5-second deadline, and B itself needs to call C, the remaining time must be recalculated and passed on to C — not the full original budget. If B has already spent 4 seconds, it should only pass 1 second on to C.

**Why this matters:** without this propagation, a service could keep processing a request long after the client has already given up — wasted resources that become critical at the scale of thousands of requests in production.

---

## 7. Error Handling: gRPC Status Codes

gRPC uses its own status code system, distinct from HTTP codes (200, 404, 500). The most commonly used:

- `OK` — success
- `NOT_FOUND` — the requested resource does not exist
- `INVALID_ARGUMENT` — the data sent is invalid
- `DEADLINE_EXCEEDED` — the allotted time budget was exceeded

These codes are structured and travel with the response, letting the client react precisely based on the nature of the error — unlike a generic HTTP status code.

---

## 8. gRPC Compared to Alternatives

### 8.1 gRPC vs REST vs GraphQL vs WebSocket

These are different categories, often confused with one another:

| | Category | Answers |
|---|---|---|
| REST | API architectural style | How to organize resources over HTTP |
| GraphQL | API query language | How the client requests exactly the fields it needs |
| gRPC | RPC framework | How to call a remote function like a local one |
| WebSocket | Transport protocol | How to keep a bidirectional connection open |

gRPC, REST, and GraphQL are comparable to one another (three competing API philosophies). WebSocket sits at a lower transport layer, on top of which any of these styles could technically be built.

### 8.2 gRPC streaming vs WebSocket

| | WebSocket | gRPC Streaming |
|---|---|---|
| Protocol | Separate, after an HTTP/1.1 upgrade | Stays within HTTP/2 |
| Format | Free-form | Structured and typed (Protobuf) |
| Multiplexing | One connection = one channel | Multiple streams on one connection |
| Browser support | Native | Requires gRPC-Web + a proxy |
| Primary use case | Web client ↔ server | Service ↔ service (backend) |

### 8.3 Why gRPC has limited browser adoption

gRPC needs low-level control over HTTP/2 (trailers, precise framing) that browser JavaScript APIs (`fetch`, `XMLHttpRequest`) don't expose. **gRPC-Web** works around this via a proxy (commonly Envoy) that translates between the browser and the native gRPC server — an extra layer of infrastructure complexity that limits adoption on the web frontend, where REST/JSON remains dominant.

---

## 9. The Project: Order Service ↔ Payment Service

### 9.1 Architecture

```
┌─────────────────┐    gRPC (unary)         ┌───────────────────┐
│  Order Service   │ ───────────────────────▶│  Payment Service   │
│                  │◀─────────────────────── │                    │
└─────────────────┘                          └───────────────────┘
        ▲
        │ grpcurl (test client)
```

### 9.2 Defined contracts

**`order.proto`**: `CreateOrder` (unary), `GetOrder` (unary), `WatchOrderStatus` (server streaming)

**`payment.proto`**: `ProcessPayment` (unary)

### 9.3 Concepts demonstrated

- Defining `.proto` contracts and compiling them with `protoc`
- Unary and server-streaming calls
- Error handling with gRPC status codes (`NOT_FOUND`)
- Service-to-service communication with no dependency on an external HTTP framework (no FastAPI/uvicorn — `grpcio` provides its own server runtime)

---

## 10. Conclusion

gRPC is built on a simple but powerful idea: making a network call look like a local function call. This apparent simplicity rests on two independent pillars — **Protocol Buffers** to define and serialize data, **HTTP/2** to transport it efficiently — along with robustness mechanisms (deadlines, status codes) that matter precisely because a remote call is, fundamentally, never quite the same as a local one.