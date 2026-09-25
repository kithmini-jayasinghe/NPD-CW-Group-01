import socket
import sys
import argparse

def fetch_status(host, port):
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(3.0)
    
    try:
        print(f"Connecting to NetWatch status server at {host}:{port}...")
        client.connect((host, port))
        
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
        print(f"Error: Connection refused. Is status_server.py running on port {port}?")
        sys.exit(1)
    except socket.timeout:
        print(f"Error: Connection to {host}:{port} timed out.")
        sys.exit(1)
    except (OSError, UnicodeDecodeError) as error:
        print(f"An error occurred: {error}")
        sys.exit(1)
    finally:
        client.close()
        print("Socket connection closed cleanly.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read the NetWatch status page")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8888)
    args = parser.parse_args()
    fetch_status(args.host, args.port)
