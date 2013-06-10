from unittest import TestCase
from main import CallbackWSGIApplication, SpawningWSGIServer
import gevent


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

        paths = ('/world/', '/world2/')
        jobs = [self.app.register_listener(path, listener) for path in paths]
        gevent.joinall(jobs, 10)  # Visit both http://localhost:8080/world/ and http://localhost:8080/world/ within
                                  # 10 secs, otherwise the test will fail

        for job, path in zip(jobs, paths):
            request = job.value
            self.assertIsNotNone(request)  # Fails if endpoint was not visited
            self.assertEqual(request.path, path)
