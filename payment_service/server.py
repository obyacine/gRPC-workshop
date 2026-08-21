import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'generated'))
import payment_pb2
import payment_pb2_grpc
import uuid
import grpc
from concurrent import futures




class  PaymentServiceServicer(payment_pb2_grpc.PaymentServiceServicer):
    def ProcessPayment(self,request,context):
        if request.amount<=0:
            return payment_pb2.PaymentResponse(
                success=False,
                message="enter a valid number",
                transaction_id="",
            )

        else :
            return payment_pb2.PaymentResponse(
                success=True,
                message="payment done",
                transaction_id=str(uuid.uuid4()),


            )

        
    
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    payment_pb2_grpc.add_PaymentServiceServicer_to_server(PaymentServiceServicer(), server)
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Payment Service démarré sur le port 50052")
    server.wait_for_termination()

if __name__ == '__main__':
    serve()




     
            


        
        


