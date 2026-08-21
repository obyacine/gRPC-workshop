import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated'))

import grpc
from concurrent import futures
import order_pb2
import order_pb2_grpc
import payment_pb2
import payment_pb2_grpc
import uuid
import time

orders_db = {}

class OrderServiceServicer(order_pb2_grpc.OrderServiceServicer):
    def CreateOrder(self, request, context):
        order_id = str(uuid.uuid4())

        channel = grpc.insecure_channel('localhost:50052')
        stub = payment_pb2_grpc.PaymentServiceStub(channel)
        payment_response = stub.ProcessPayment(
            payment_pb2.PaymentRequest(order_id=order_id, amount=request.amount)
        )

        status = "PAID" if payment_response.success else "FAILED"

        order = order_pb2.Order(
            order_id=order_id,
            user_id=request.user_id,
            amount=request.amount,
            status=status,
        )
        orders_db[order_id] = order
        return order

    def GetOrder(self, request, context):
        if request.order_id not in orders_db:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Commande introuvable")
            return order_pb2.Order()
        return orders_db[request.order_id]

    def WatchOrderStatus(self, request, context):
        if request.order_id not in orders_db:
            context.set_code(grpc.StatusCode.NOT_FOUND)
            context.set_details("Commande introuvable")
            return

        statuses = ["PENDING", "PROCESSING", orders_db[request.order_id].status]

        for status in statuses:
            order = orders_db[request.order_id]
            order.status = status
            yield order
            time.sleep(1)

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    order_pb2_grpc.add_OrderServiceServicer_to_server(OrderServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Order Service démarré sur le port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()


