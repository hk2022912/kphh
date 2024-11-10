# wifimgr.py

import network
import socket
import ure
import time
import os 

ap_ssid = "KPHH-AP"
ap_password = "12345678"
ap_authmode = 3  # WPA2

NETWORK_PROFILES = 'wifi.dat'

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)

server_socket = None


def get_connection():
    """return a working WLAN(STA_IF) instance or None"""

    if wlan_sta.isconnected():
        return wlan_sta

    connected = False
    try:
        time.sleep(3)
        if wlan_sta.isconnected():
            return wlan_sta

        profiles = read_profiles()
        wlan_sta.active(True)
        networks = wlan_sta.scan()

        AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
        for ssid, bssid, channel, rssi, authmode, hidden in sorted(networks, key=lambda x: x[3], reverse=True):
            ssid = ssid.decode('utf-8')
            encrypted = authmode > 0
            print("ssid: %s chan: %d rssi: %d authmode: %s" % (ssid, channel, rssi, AUTHMODE.get(authmode, '?')))
            if encrypted:
                if ssid in profiles:
                    password = profiles[ssid]
                    connected = do_connect(ssid, password)
                else:
                    print("skipping unknown encrypted network")
            else:  # open
                connected = do_connect(ssid, None)
            if connected:
                break

    except OSError as e:
        print("exception", str(e))

    if not connected:
        connected = start()

    return wlan_sta if connected else None


def read_profiles():
    with open(NETWORK_PROFILES) as f:
        lines = f.readlines()
    profiles = {}
    for line in lines:
        ssid, password = line.strip("\n").split(";")
        profiles[ssid] = password
    return profiles


def write_profiles(profiles):
    lines = []
    for ssid, password in profiles.items():
        lines.append("%s;%s\n" % (ssid, password))
    with open(NETWORK_PROFILES, "w") as f:
        f.write(''.join(lines))


def do_connect(ssid, password):
    wlan_sta.active(True)
    if wlan_sta.isconnected():
        return None
    print('Trying to connect to %s...' % ssid)
    wlan_sta.connect(ssid, password)
    for retry in range(200):
        connected = wlan_sta.isconnected()
        if connected:
            break
        time.sleep(0.1)
        print('.', end='')
    if connected:
        print('\nConnected. Network config: ', wlan_sta.ifconfig())
    else:
        print('\nFailed. Not Connected to: ' + ssid)
    return connected


def send_header(client, status_code=200, content_length=None):
    client.sendall("HTTP/1.0 {} OK\r\n".format(status_code))
    client.sendall("Content-Type: text/html\r\n")
    if content_length is not None:
        client.sendall("Content-Length: {}\r\n".format(content_length))
    client.sendall("\r\n")


def send_response(client, payload, status_code=200):
    content_length = len(payload)
    send_header(client, status_code, content_length)
    if content_length > 0:
        client.sendall(payload)
    client.close()


def handle_root(client):
    wlan_sta.active(True)
    ssids = sorted(ssid.decode('utf-8') for ssid, *_ in wlan_sta.scan())
    send_header(client)
    client.sendall("""\
        <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
                .container { max-width: 100%; padding: 10px; text-align: center; }
                .title { display: flex; justify-content: center; align-items: center; }
                h1 { color: #5e9ca0; font-size: 24px; margin-right: 10px; }
                .title img { max-width: 50px; height: auto; border-radius: 30px; margin-right: 10px;}
                .title h2 { color: #5e9ca0; color: #5e9ca0; }
                form { margin: 20px auto; max-width: 300px; width: 100%; }
                input[type="radio"] { margin-bottom: 10px; }
                input[type="password"], input[type="submit"] { width: 100%; padding: 8px; margin-top: 10px; border: 1px solid #ccc; border-radius: 4px; }
                table { width: 100%; margin: auto; }
                td { padding: 5px; }
                h5 { font-size: 12px; color: #ff0000; margin: 10px; }
                hr { margin: 20px 0; }
                ul { padding-left: 20px; text-align: left; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="title">
                    <img src="/img.png" alt="Logo">
                    <h2> KPHH </h2>
                </div>
                <h1>Wi-Fi Client Setup</h1>
                <form action="configure" method="post">
                    <table>
                        <tbody>
    """)

    while len(ssids):
        ssid = ssids.pop(0)
        client.sendall(f"""
                            <tr>
                                <td colspan="2">
                                    <input type="radio" name="ssid" value="{ssid}" /> {ssid}
                                </td>
                            </tr>
        """)

    client.sendall("""\
                            <tr>
                                <td>Password:</td>
                                <td><input name="password" type="password" /></td>
                            </tr>
                        </tbody>
                    </table>
                    <input type="submit" value="Submit">
                </form>
                <hr />
            </div>
        </body>
        </html>
    """)
    client.close()


def handle_configure(client, request):
    match = ure.search("ssid=([^&]*)&password=(.*)", request)

    if match is None:
        send_response(client, "Parameters not found", status_code=400)
        return False

    try:
        ssid = match.group(1).decode("utf-8").replace("%3F", "?").replace("%21", "!")
        password = match.group(2).decode("utf-8").replace("%3F", "?").replace("%21", "!")
    except Exception:
        ssid = match.group(1).replace("%3F", "?").replace("%21", "!")
        password = match.group(2).replace("%3F", "?").replace("%21", "!")

    # Check if SSID is provided
    if len(ssid) == 0:
        send_response(client, "SSID must be provided", status_code=400)
        return False

    # Attempt to connect to the specified SSID
    connected = do_connect(ssid, password)
    if connected:
        response = """\
            <html>
                <center>
                    <br><br>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP successfully connected to WiFi network {ssid}.
                        </span>
                    </h1>
                    <br><br>
                </center>
            </html>
        """.format(ssid=ssid)
        send_response(client, response)

        # Save the profile if successfully connected
        time.sleep(1)  # Brief pause before disabling AP
        wlan_ap.active(False)
        
        # Read existing profiles and add new one
        try:
            profiles = read_profiles()
        except OSError:
            profiles = {}

        # Update profiles with new SSID and password
        profiles[ssid] = password
        write_profiles(profiles)

        time.sleep(5)  # Delay to allow for new connection
        return True
    else:
        response = """\
            <html>
                <center>
                    <h1 style="color: #5e9ca0; text-align: center;">
                        <span style="color: #ff0000;">
                            ESP could not connect to WiFi network {ssid}. Please check the password and try again.
                        </span>
                    </h1>
                    <br><br>
                    <form>
                        <input type="button" value="Go back!" onclick="history.back()"></input>
                    </form>
                </center>
            </html>
        """.format(ssid=ssid)
        send_response(client, response)
        return False

def handle_image(client):
    """Serve the image file in chunks from LittleFS"""
    try:
        file_path = '/data/img.png'
        file_size = os.stat(file_path)[6]  # Get file size
        send_header(client, content_length=file_size)
        
        with open(file_path, 'rb') as f:
            chunk_size = 4096  # Send 4KB at a time for better performance
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                client.sendall(chunk)  # Send the chunk

        print("Image sent successfully.")

    except OSError:
        print("Error: Image file not found.")
        send_response(client, "Image file not found", status_code=404)
    except MemoryError:
        print("Memory allocation error while sending image.")
        send_response(client, "Memory allocation error", status_code=500)
    except Exception as e:
        print("Error sending image:", str(e))
        send_response(client, "Error sending image", status_code=500)

def handle_not_found(client, url):
    send_response(client, "Path not found: {}".format(url), status_code=404)


def stop():
    global server_socket

    if server_socket:
        server_socket.close()
        server_socket = None


def start(port=80):
    global server_socket

    addr = socket.getaddrinfo('0.0.0.0', port)[0][-1]

    stop()

    wlan_sta.active(True)
    wlan_ap.active(True)

    wlan_ap.config(essid=ap_ssid, password=ap_password, authmode=ap_authmode)

    server_socket = socket.socket()
    server_socket.bind(addr)
    server_socket.listen(1)

    print('Connect to WiFi ssid ' + ap_ssid + ', default password: ' + ap_password)
    print('and access the ESP via your favorite web browser at 192.168.4.1.')
    print('Listening on:', addr)

    while True:
        if wlan_sta.isconnected():
            wlan_ap.active(False)
            return True

        client, addr = server_socket.accept()
        print('client connected from', addr)
        try:
            client.settimeout(5.0)

            request = b""
            try:
                while "\r\n\r\n" not in request:
                    request += client.recv(512)
            except OSError:
                pass

            # Handle form data from Safari on macOS and iOS; it sends \r\n\r\nssid=<ssid>&password=<password>
            try:
                request += client.recv(1024)
                print("Received form data after \\r\\n\\r\\n(i.e. from Safari on macOS or iOS)")
            except OSError:
                pass

            print("Request is: {}".format(request))
            if "HTTP" not in request:  # skip invalid requests
                continue

            # version 1.9 compatibility
            try:
                url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).decode("utf-8").rstrip("/")
            except Exception:
                url = ure.search("(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP", request).group(1).rstrip("/")
            print("URL is {}".format(url))

            if url == "":
                handle_root(client)
            elif url == "configure":
                handle_configure(client, request)
            elif url == "img.png":
                handle_image(client)
            else:
                handle_not_found(client, url)

        except Exception as e:
            print("Error processing request:", str(e))

        finally:
            client.close()

def main():
    # Initialize LittleFS (Make sure it's supported in your firmware)
    os.mount(os.VfsLittleFS(), "/data")  # Mount LittleFS on /data

    # Get the connection
    get_connection()

    if __name__ == "__main__":
        main()
