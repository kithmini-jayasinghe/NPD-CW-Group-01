import socket
import sys

HOST = "127.0.0.1"
PORT = 8888

def fetch_status():
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(3.0)
    
    try:
        print(f"Connecting to NetWatch status server at {HOST}:{PORT}...")
        client.connect((HOST, PORT))
        
        # Send HTTP GET request
        request = "GET / HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        client.sendall(request.encode("utf-8"))
        
        # Receive binary response
        response = b""
        while True:
            data = client.recv(1024)
            if not data:
                break
            response += data
            
        print("\n--- Received Server Reply ---")
        # Convert bytes to text using .decode()
        print(response.decode("utf-8"))
        print("-----------------------------\n")
        
    except ConnectionRefusedError:
        print(f"Error: Connection refused. Is status_server.py running on port {PORT}?")
        sys.exit(1)
    except socket.timeout:
        print(f"Error: Connection to {HOST}:{PORT} timed out.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        client.close()
        print("Socket connection closed cleanly.")

if __name__ == "__main__":
    fetch_status()
