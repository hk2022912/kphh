# main.py
import wifimgr
import socket
import machine
import gc 

# Connect to WiFi
wlan = wifimgr.get_connection()
if wlan is None:
    print("Could not initialize the network connection.")
    while True:
        pass  # you shall not pass :D

print("ESP OK")  # WLAN is connected

# Web page function
def web_page(led_state):
    html = """<html><head> <title>ESP Web Server</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="icon" href="data:,"> <style>
    html{font-family: Helvetica; display:inline-block; margin: 0px auto; text-align: center;}
    h1{color: #0F3376; padding: 2vh;}p{font-size: 1.5rem;}.button{
    display: inline-block; background-color: #e7bd3b; border: none; 
    border-radius: 4px; color: white; padding: 16px 40px; text-decoration: none; font-size: 30px; margin: 2px; cursor: pointer;}
    .button2{background-color: #4286f4;}</style></head><body>
    <h1>ESP Web Server</h1> 
    <p>GPIO state: <strong>""" + led_state + """</strong></p>
    <p><a href="/?led=on"><button class="button">ON</button></a></p>
    <p><a href="/?led=off"><button class="button button2">OFF</button></a></p>
    </body></html>"""
    return html

# Create a socket for the web server
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('', 80))
    s.listen(5)
except OSError as e:
    machine.reset()

led = machine.Pin(2, machine.Pin.OUT)  # Change pin number as needed
led.value(0)  # Initialize LED state to OFF

while True:
    try:
        if gc.mem_free() < 102000:
            gc.collect()

        conn, addr = s.accept()
        conn.settimeout(3.0)
        print('Got a connection from %s' % str(addr))
        request = conn.recv(1024)
        conn.settimeout(None)
        request = str(request)
        print('Content = %s' % request)

        led_on = request.find('/?led=on')
        led_off = request.find('/?led=off')

        if led_on != -1:
            print('LED ON')
            led.value(1)
        elif led_off != -1:
            print('LED OFF')
            led.value(0)

        # Prepare the response
        led_state = "ON" if led.value() == 1 else "OFF"
        response = web_page(led_state)

        # Send HTTP response
        conn.send('HTTP/1.1 200 OK\n')
        conn.send('Content-Type: text/html\n')
        conn.send('Connection: close\n\n')
        conn.sendall(response)
        conn.close()
    except OSError as e:
        conn.close()
        print('Connection closed')
