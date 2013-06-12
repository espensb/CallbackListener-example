from unittest import TestCase
from main import CallbackWSGIApplication
from main import SpawningWSGIServer
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
        def listener(request, response, id):
            response.write('Hello ' + id)
            return id

        def other_listener(request, response, id):
            response.write('Foo' + id)
            return id

        ids = ('world', 'world2', 'world')
        listeners = (listener, listener, other_listener)
        listener_jobs = [self.app.add_listener('/<id:%s>/' % id, l) for id, l in zip(ids, listeners)]
        request_jobs = [gevent.spawn(urllib.urlopen, 'http://localhost:8080/%s/' % id) for id in ids]
        gevent.joinall(listener_jobs + request_jobs, 10)  # Timeout after 10 secs if HTTP requests were not received.

        for job, id in zip(listener_jobs, ids):
            self.assertTrue(job.ready())
            id = job.value
            self.assertIsNotNone(id, '%s was not called' % id)  # Fails if endpoint was not visited
            self.assertEqual(id, id)
