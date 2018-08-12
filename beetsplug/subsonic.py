# Subsonic plugin for Beets
# Allows to trigger a library scan on Subsonic after music has been imported with Beets
# Your Beets configuration file should contain a subsonic section like the following:
#    subsonic:
#        host: 192.168.x.y (the IP address where Subsonic listens on)
#        port: 4040 (default)
#        user: <your username>
#        pass: <your password>
# Plugin wrote by Lorenzo Maffeo 

from beets.plugins import BeetsPlugin
import requests
import string
import hashlib
from random import *

class Subsonic(BeetsPlugin):
  def __init__(self):
    super(Subsonic, self).__init__()
    self.register_listener('import', self.loaded)

  def loaded(self):
    host = self.config['host'].get()
    port = self.config['port'].get()
    user = self.config['user'].get()
    passw = self.config['pass'].get()
    url = "http://"+str(host)+":"+str(port)+"/rest/startScan"
    salt = "".join([random.choice(string.ascii_letters + string.digits) for n in range(6)])
    t = passw + salt
    token = hashlib.md5()
    token.update(t.encode('utf-8'))
    payload = {
	'u': user,
	't': token.hexdigest(),
	's': salt,
	'v': '1.15.0',
	'c': 'beets'
	}
    response = requests.post(url, params=payload)
    if (response.status_code == 0):
      self._log.error(u'Operation Failed due to a generic error, please try again later.') 
      print("Operation Failed due to a generic error, please try again later.")
    elif (response.status_code == 30):
      self._log.error(u'Your Subsonic server version is not compatible with this feature, please upgrade to at least version 6.1 (API version 1.15.0).')        
      print("Your Subsonic server version is not compatible with this feature, please upgrade to at least v
ersion 6.1 (API version 1.15.0).") 
    elif (response.status_code == 40):
      self._log.error(u'Wrong username or password. Check and update the credentials in your Beets configuration file.')        
      print("Wrong username or password. Check and update the credentials in your Beets configuration file.") 
    elif (response.status_code == 50):
      self._log.error(u'User %s is not allowed to perform the requested operation.', user) 
      print("User " + str(user) + "is not allowed to perform the requested operation.")        
    elif (response.status_code == 60):
      self._log.error(u'This feature requires Subsonic Premium, check that your license is still valid or the trial period has not expired.')         
      print("This feature requires Subsonic Premium, check that your license is still valid or the trial pe
riod has not expired.")
    elif (response.status_code == 200):
      self._log.info('Operation completed successfully!")
      print("Operation completed successfully!")
    else
      self._log.error(u'Unknown error code returned from server.')
      print("Unknown error code returned from server.")
