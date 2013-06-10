"""
Usage: Start script, then use you web browser, wget, etc. to visit:
    http://localhost:8080/world/
    http://localhost:8080/world2/
"""

from gevent.monkey import patch_all
patch_all()
import gevent
from gevent import wsgi
from gevent.event import AsyncResult
import urllib
import webapp2


class EventLoopRequestContext(webapp2.RequestContext):
    """
    Override webapp2.RequestContext in order to avoid setting thread-local variables, since we're always working
    in a single thread with gevent.
    """
    def __enter__(self):
        """
        Same as in webapp2.RequestContext, except that thread-local variables are not set.
        """
        request = self.app.request_class(self.environ)
        response = self.app.response_class()
        # Make active app and response available through the request object.
        request.app = self.app
        request.response = response
        return request, response

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Skipping thread-local tear-down
        """
        pass


class ListenerRouter(object):
    """
    A faster Router that looks up a static path definition in a dict instead of iterating through webapp routes.
    """
    def __init__(self, routes):
        pass

    def dispatch(self, request, response):
        path = urllib.unquote(request.path)
        queue = request.app.listeners.get(path)
        if not queue:  # is queue None or empty?
            response.clear()
            return response  # May instead raise HTTPNotFound here
        listener, async_result = queue.pop(0)
        res = listener(request, response, path)
        print "SETTING VALUE"
        async_result.set(res)
        print "COMPLETING RESPONSE"
        return response


class CallbackWSGIApplication(webapp2.WSGIApplication):
    listeners = {}
    request_context_class = EventLoopRequestContext
    router_class = ListenerRouter

    def __init__(self, debug=False, config=None):
        super(CallbackWSGIApplication, self).__init__(routes=None, debug=debug, config=config)

    @classmethod
    def spawn(cls, hostport):
        return gevent.spawn()

    def add_listener(self, path, listener):
        async_result = AsyncResult()
        queue = self.listeners.get(path)
        if queue is None:
            self.listeners[path] = queue = []
        queue.append((listener, async_result))

        def get_res():
            print "LISTENING TO:", path
            res = async_result.get()  # This will block until async_result.set() has been called some other place
            print "GOT REQUEST ON:", path
            gevent.sleep()  # Yield control to event-loop so that the CallbackWSGIApplication is
                            # able to receive the next request
            print "WAKING"
            return res
        return gevent.spawn(get_res)


class SpawningWSGIServer(wsgi.WSGIServer):
    server_job = None

    def serve_forever(self, stop_timeout=None):
        if self.server_job is None:
            self.server_job = gevent.spawn(super(SpawningWSGIServer, self).serve_forever)

    def stop(self, timeout=None):
        super(SpawningWSGIServer, self).stop(timeout=timeout)
        if self.server_job is not None:
            self.server_job.join()


if __name__ == '__main__':
    application = CallbackWSGIApplication()
    server = SpawningWSGIServer(('', 8080), application)
    try:
        server.serve_forever()
        print "SPAWNED SERVER"

        def listener(request, response, path):
            response.write('Hello ' + path.replace('/', ' '))
            return request

        world_job = application.add_listener('/world/', listener)
        world2_job = application.add_listener('/world2/', listener)

        gevent.joinall((world_job, world2_job))  # Blocking until GET has been called on both '/world/' and '/world2/'
        print "RES 1:", world_job.value
        print "RES 2:", world2_job.value
    finally:
        server.stop()

