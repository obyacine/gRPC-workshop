# grpc-workshop
 
A minimal two-service system built with gRPC to demonstrate core concepts: unary RPC, server streaming, service-to-service communication, and error handling — built as part of MicroClub's **IT Blackout** challenge.
 
## Overview
 
Two independent gRPC services communicate to simulate a simple order/payment flow:
 
```
┌──────────────────┐   gRPC (unary)    ┌────────────────────┐
│   Order Service   │ ────────────────▶ │   Payment Service   │
│   (port 50051)    │ ◀──────────────── │   (port 50052)      │
└──────────────────┘                    └────────────────────┘
        ▲
        │ grpcurl / client
```
 
- **Order Service** owns order creation, retrieval, and status tracking.
- **Payment Service** processes payments and is called internally by Order Service.
## Services
 
### OrderService (`proto/order.proto`)
 
| RPC | Type | Description |
|---|---|---|
| `CreateOrder` | Unary | Creates an order, triggers a payment via Payment Service, returns the created `Order` |
| `GetOrder` | Unary | Retrieves an order by `order_id`; returns `NOT_FOUND` if it doesn't exist |
| `WatchOrderStatus` | Server streaming | Streams status updates for a given order over time |
 
### PaymentService (`proto/payment.proto`)
 
| RPC | Type | Description |
|---|---|---|
| `ProcessPayment` | Unary | Validates and processes a payment, returns success/failure with a transaction ID |
 
## Tech stack
 
- Python 3.9
- `grpcio` / `grpcio-tools` — no web framework involved (no FastAPI/uvicorn); gRPC ships its own server runtime
- In-memory storage (a plain dict) — no database, by design, to keep the focus on gRPC itself
## Project structure
 
```
grpc-workshop/
├── proto/
│   ├── order.proto
│   └── payment.proto
├── generated/          # generated from .proto files, not hand-edited
├── order_service/
│   └── server.py
├── payment_service/
│   └── server.py
├── requirements.txt
└── README.md
```
 
## Setup
 
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
 
## Generating the gRPC code
 
Whenever `proto/*.proto` changes, regenerate the Python bindings:
 
```bash
python -m grpc_tools.protoc \
  -I proto \
  --python_out=generated \
  --grpc_python_out=generated \
  proto/order.proto proto/payment.proto
```
 
## Running the services
 
Start each service in its own terminal (order doesn't matter, but Payment should be up before you call `CreateOrder`):
 
```bash
# Terminal 1
python payment_service/server.py
 
# Terminal 2
python order_service/server.py
```
 
## Testing with grpcurl
 
Since server reflection isn't enabled, pass the `.proto` file explicitly:
 
```bash
# Create an order (internally calls Payment Service)
grpcurl -plaintext -import-path proto -proto order.proto \
  -d '{"user_id": "yacine", "amount": 50}' \
  localhost:50051 OrderService/CreateOrder
 
# Fetch an order by ID
grpcurl -plaintext -import-path proto -proto order.proto \
  -d '{"order_id": "<order_id_from_above>"}' \
  localhost:50051 OrderService/GetOrder
 
# Watch status updates (server streaming)
grpcurl -plaintext -import-path proto -proto order.proto \
  -d '{"order_id": "<order_id_from_above>"}' \
  localhost:50051 OrderService/WatchOrderStatus
 
# Call Payment Service directly
grpcurl -plaintext -import-path proto -proto payment.proto \
  -d '{"order_id": "42", "amount": 99.9}' \
  localhost:50052 PaymentService/ProcessPayment
```