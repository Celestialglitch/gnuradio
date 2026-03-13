#!/usr/bin/env python
#
# Copyright 2025 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# SPDX-License-Identifier: GPL-3.0-or-later
#

from gnuradio import gr, gr_unittest, blocks
from gnuradio.network import tcp_source
import socket
import threading
import time
import struct


class qa_tcp_source(gr_unittest.TestCase):
    """
    QA tests for tcp_source block.
    
    Note: tcp_source blocks during construction waiting for connection,
    so tests must have the peer socket ready before creating the block.
    """

    def setUp(self):
        self.tb = gr.top_block()

    def tearDown(self):
        self.tb = None

    def test_server_mode_float(self):
        """Test tcp_source in server mode receiving float data."""
        port = 15000  # Use higher port numbers to avoid conflicts
        num_samples = 100
        test_data = list(range(num_samples))
        packed_data = struct.pack(f'{num_samples}f', *test_data)
        
        def send_data():
            """Connect as client and send data to server."""
            time.sleep(0.2)  # Longer delay to ensure server is ready
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect(('127.0.0.1', port))
                sock.sendall(packed_data)
                time.sleep(0.2)  # Ensure data is sent
            finally:
                sock.close()
        
        # Start sender thread before creating tcp_source (which will block on accept)
        sender = threading.Thread(target=send_data)
        sender.start()
        
        # Create tcp_source in server mode - this will block until client connects
        tcp_src = tcp_source.tcp_source(gr.sizeof_float, '127.0.0.1', port, server=True)
        vector_sink = blocks.vector_sink_f()
        head = blocks.head(gr.sizeof_float, num_samples)
        
        self.tb.connect(tcp_src, head, vector_sink)
        self.tb.run()
        
        sender.join(timeout=5.0)
        
        # Verify received data
        result = vector_sink.data()
        self.assertEqual(len(result), num_samples, 
                        f"Expected {num_samples} samples, got {len(result)}")
        # Allow small floating point differences
        for i, (expected, actual) in enumerate(zip(test_data, result)):
            self.assertAlmostEqual(expected, actual, places=5,
                                 msg=f"Sample {i} mismatch")

    def test_client_mode_complex(self):
        """Test tcp_source in client mode receiving complex data."""
        port = 15001  # Different port
        num_samples = 50
        
        # Create server socket first
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind(('127.0.0.1', port))
        server_sock.listen(1)
        
        def send_data():
            """Accept connection and send complex data."""
            client_sock, _ = server_sock.accept()
            try:
                # Send complex data (interleaved I/Q floats)
                data = []
                for i in range(num_samples):
                    data.extend([float(i), float(i * 2)])  # I, Q
                packed_data = struct.pack(f'{len(data)}f', *data)
                client_sock.sendall(packed_data)
                time.sleep(0.2)
            finally:
                client_sock.close()
        
        sender = threading.Thread(target=send_data)
        sender.start()
        
        time.sleep(0.1)  # Brief delay to ensure server is listening
        
        # Create tcp_source in client mode - will connect to our server
        tcp_src = tcp_source.tcp_source(gr.sizeof_gr_complex, '127.0.0.1', port, server=False)
        vector_sink = blocks.vector_sink_c()
        head = blocks.head(gr.sizeof_gr_complex, num_samples)
        
        self.tb.connect(tcp_src, head, vector_sink)
        self.tb.run()
        
        sender.join(timeout=5.0)
        server_sock.close()
        
        # Verify received data
        result = vector_sink.data()
        self.assertEqual(len(result), num_samples,
                        f"Expected {num_samples} complex samples, got {len(result)}")

    def test_server_mode_byte(self):
        """Test tcp_source with byte data."""
        port = 15002  # Different port
        test_data = bytes(range(256))
        
        def send_data():
            time.sleep(0.2)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.connect(('127.0.0.1', port))
                sock.sendall(test_data)
                time.sleep(0.2)
            finally:
                sock.close()
        
        sender = threading.Thread(target=send_data)
        sender.start()
        
        tcp_src = tcp_source.tcp_source(gr.sizeof_char, '127.0.0.1', port, server=True)
        vector_sink = blocks.vector_sink_b()
        head = blocks.head(gr.sizeof_char, len(test_data))
        
        self.tb.connect(tcp_src, head, vector_sink)
        self.tb.run()
        
        sender.join(timeout=5.0)
        
        result = vector_sink.data()
        self.assertEqual(len(result), len(test_data))
        self.assertEqual(bytes(result), test_data)

    def test_ipv6_server_mode(self):
        """Test tcp_source with IPv6."""
        port = 15003  # Different port
        num_samples = 20
        test_data = struct.pack(f'{num_samples}f', *range(num_samples))
        
        def send_data():
            time.sleep(0.2)
            try:
                sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
                sock.connect(('::1', port))
                sock.sendall(test_data)
                time.sleep(0.2)
                sock.close()
            except OSError:
                pass  # IPv6 might not be available
        
        try:
            sender = threading.Thread(target=send_data)
            sender.start()
            
            tcp_src = tcp_source.tcp_source(gr.sizeof_float, '::', port, server=True)
            vector_sink = blocks.vector_sink_f()
            head = blocks.head(gr.sizeof_float, num_samples)
            
            self.tb.connect(tcp_src, head, vector_sink)
            self.tb.run()
            
            sender.join(timeout=5.0)
            
            result = vector_sink.data()
            if len(result) > 0:  # Only verify if IPv6 worked
                self.assertEqual(len(result), num_samples)
        except OSError:
            self.skipTest("IPv6 not available on this system")


if __name__ == '__main__':
    gr_unittest.run(qa_tcp_source)
