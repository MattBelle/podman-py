import unittest

import podman.tests.integration.base as base
from podman import PodmanClient

# @unittest.skipIf(os.geteuid() != 0, 'Skipping, not running as root')


class ContainersExecIntegrationTests(base.IntegrationTest):
    """Containers integration tests for exec"""

    def setUp(self):
        super().setUp()

        self.client = PodmanClient(base_url=self.socket_uri)
        self.addCleanup(self.client.close)

        self.alpine_image = self.client.images.pull("quay.io/libpod/alpine", tag="latest")
        self.containers = []

    def tearDown(self):
        for container in self.containers:
            container.remove(force=True)

    def test_container_exec_run(self):
        """Test any command that will return code 0 and no output"""
        container = self.client.containers.create(self.alpine_image, command=["top"], detach=True)
        container.start()
        error_code, stdout = container.exec_run("echo hello")

        self.assertEqual(error_code, 0)
        self.assertEqual(stdout, b'\x01\x00\x00\x00\x00\x00\x00\x06hello\n')

    def test_container_exec_run_errorcode(self):
        """Test a failing command with stdout and stderr in a single bytestring"""
        container = self.client.containers.create(self.alpine_image, command=["top"], detach=True)
        container.start()
        error_code, output = container.exec_run("ls nonexistent")

        self.assertEqual(error_code, 1)
        self.assertEqual(
            output, b"\x02\x00\x00\x00\x00\x00\x00+ls: nonexistent: No such file or directory\n"
        )

    def test_container_exec_run_demux(self):
        """Test a failing command with stdout and stderr in a bytestring tuple"""
        container = self.client.containers.create(self.alpine_image, command=["top"], detach=True)
        container.start()
        error_code, output = container.exec_run("ls nonexistent", demux=True)

        self.assertEqual(error_code, 1)
        self.assertEqual(output[0], None)
        self.assertEqual(output[1], b"ls: nonexistent: No such file or directory\n")

    def test_container_exec_run_stream(self):
        """Test streaming the output from a long running command."""
        container = self.client.containers.create(self.alpine_image, command=["top"], detach=True)
        container.start()

        command = []
        for i in range(3):
            # We want to sleep so that the lines get  processed seperately
            command.extend(['echo', str(i), ';', 'sleep', '.1', ';'])
        command = ['/bin/sh', '-c', ' '.join(command)]
        error_code, output = container.exec_run(command, stream=True)

        self.assertEqual(error_code, None)
        for index, data in enumerate(output):
            self.assertEqual(data, f'{index}\n'.encode())

    def test_container_exec_run_stream_demux(self):
        """Test streaming the output from a long running command with demux enabled."""
        container = self.client.containers.create(self.alpine_image, command=["top"], detach=True)
        container.start()

        command = []
        for i in range(3):
            # We want to sleep so that the lines get  processed seperately
            command.extend(
                ['echo', str(i * 2), ';', '>&2', 'echo', str(i * 2 + 1), ';', 'sleep', '.1', ';']
            )
        command = ['/bin/sh', '-c', ' '.join(command)]
        error_code, output = container.exec_run(command, stream=True, demux=True)

        self.assertEqual(error_code, None)
        for index, data in enumerate(output):
            if index % 2 == 0:
                self.assertEqual(data, (f'{index}\n'.encode(), None))
            else:
                self.assertEqual(data, (None, f'{index}\n'.encode()))
