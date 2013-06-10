from unittest import TestCase
from main import CallbackWSGIApplication, SpawningWSGIServer
import gevent
import urllib


class ListenerTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ListenerTest, cls).setUpClass()
        cls.app = CallbackWSGIApplication(debug=True)
        cls.server = SpawningWSGIServer(('', 8080), cls.app)
        cls.server.serve_forever()

    @classmethod
    def tearDownClass(cls):
        super(ListenerTest, cls).tearDownClass()
        cls.server.stop()

    def test_world_and_world2_is_called(self):
        def listener(request, response, path):
            response.write('Hello ' + path.replace('/', ' '))
            return request

        paths = ('/world/', '/world2/', '/world/')
        jobs = [self.app.add_listener(path, listener) for path in paths]
        req_jobs = [gevent.spawn(urllib.urlopen, 'http://localhost:8080' + path) for path in paths]
        gevent.joinall(jobs + req_jobs, 10)  # Timeout after 10 secs if HTTP requests were not received.

        for job, path in zip(jobs, paths):
            self.assertTrue(job.ready())
            request = job.value
            self.assertIsNotNone(request, '%s was not called' % path)  # Fails if endpoint was not visited
            self.assertEqual(request.path, path)
