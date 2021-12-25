import io
import json
import os
import time

import picamera
import logging
import socketserver
from threading import Condition
from http import server
from settings import Settings

cam_settings = Settings()


class StreamingOutput(object):
    def __init__(self):
        self.frame = None
        self.buffer = io.BytesIO()
        self.condition = Condition()

    def write(self, buf):
        if buf.startswith(b'\xff\xd8'):
            # New frame, copy the existing buffer's content and notify all
            # clients it's available
            self.buffer.truncate()
            with self.condition:
                self.frame = self.buffer.getvalue()
                self.condition.notify_all()
            self.buffer.seek(0)
        return self.buffer.write(buf)


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_POST(self):
        content = self.handle_post().encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(content))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path.endswith(".html"):
            file = open("www" + self.path, "r")
            content = file.read().encode('utf-8')
            file.close()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path.endswith(".js"):
            file = open("www/js" + self.path, "r")
            content = file.read().encode('utf-8')
            file.close()
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path.endswith(".png"):
            file = open("www/img" + self.path, "rb")
            content = file.read()
            file.close()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path.endswith(".json"):
            content = self.handle_get().encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()
            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning(
                    'Removed streaming client %s: %s',
                    self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

    def handle_get(self):
        if self.path == '/power_off.json':
            os.system("shutdown now")
            return '{"message": "Powering Off"}'
        elif self.path == '/get_all_settings.json':
            return cam_settings.get_all_settings()
        elif self.path == '/take_photo.json':
            view_camera.stop_recording()
            filename = 'data/captures/' + (str(time.time()).replace(".", "_")) + '.jpg'
            try:
                view_camera.resolution = (cam_settings.get_property("still", "width"),
                                          cam_settings.get_property("still", "height"))
                view_camera.capture(filename)
                print("Image Captured!")
            finally:
                view_camera.resolution = (cam_settings.get_property("display", "width"),
                                          cam_settings.get_property("display", "height"))
                view_camera.framerate = cam_settings.get_property("display", "framerate")
                view_camera.start_recording(output, format='mjpeg')
            return '{"message": "File Captured ' + filename + '"}'
        else:
            return '{"message": "method_not_found"}'

    def handle_post(self):
        content_len = int(self.headers.get('content-length', 0))
        if self.path == '/save_settings':
            data = json.loads(self.rfile.read(content_len).decode())
            for prop in data:
                parts = prop.split(".")
                cam_settings.set_property(parts[0], parts[1], data[prop])
            return '{"message": "Save Successful"}'
        else:
            return '{"message": "method_not_found"}'


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


with picamera.PiCamera() as view_camera:
    view_camera.resolution = (cam_settings.get_property("display", "width"),
                              cam_settings.get_property("display", "height"))
    view_camera.framerate = cam_settings.get_property("display", "framerate")
    output = StreamingOutput()
    view_camera.start_recording(output, format='mjpeg')
    try:
        address = ('', 80)
        server = StreamingServer(address, StreamingHandler)
        server.serve_forever()
    finally:
        view_camera.stop_recording()
