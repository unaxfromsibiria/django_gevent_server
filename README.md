Dependencies
=====
- `psutil https://pypi.python.org/pypi/psutil`_
- `procname https://pypi.python.org/pypi/procname/`_

Usage
=====
Append this application to INSTALLED_APPS

Create configuration section in django settings

	GEVENT_SERVER = {
	    'host': '127.0.0.1',
	    'ports': (8880, 8881, 8882),
	    'name': 'my-web-server',
	    'background': True,
	    'background_server': [
	        'project.service.warm_cache',],
	}

And run web-server:

	$./manage.py gevent_server start

will create 3 fork on each port: 8880, 8881, 8882

You can create function for background processing like this:

	def warm_cache(uid):
	    # create once subprocess
	    if '0' not in uid:
	        return
	
	    import gevent
	
	    while True:
	        # do any think
	        print 'I run every second!'
	        gevent.sleep(1.0)

good luck