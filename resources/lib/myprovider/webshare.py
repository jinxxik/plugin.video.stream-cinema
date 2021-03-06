# -*- coding: UTF-8 -*-
#/*
# *      Copyright (C) 2013 Libor Zoubek
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# */
from crypto.md5crypt import md5crypt
from datetime import timedelta
import elementtree.ElementTree as ET
import hashlib
from provider import ResolveException
import traceback
import urlparse
import util
from resources.lib.sctop import post
import xbmcgui


class Webshare():

    def __init__(self,username=None,password=None,cache=None):
        self.username = username
        self.password = password
        self.base_url = 'http://webshare.cz/'
        self.cache = cache
        self.win = xbmcgui.Window(10000)
        self.getToken()
        
    def _url(self, url):
        if url.startswith('http'):
            return url
        return self.base_url + url.lstrip('./')

    def _create_request(self, url, base):
        args = dict(urlparse.parse_qsl(url))
        headers = {'X-Requested-With':'XMLHttpRequest','Accept':'text/xml; charset=UTF-8','Referer':self.base_url}
        req = base.copy()
        for key in req:
            if key in args:
                req[key] = args[key]
        return headers,req

    def login(self):
        if not self.username or not self.password:
            self.logout()
            return True # fall back to free account
        elif self.token is not None:
            if self.userData() is not False:
                return True
            self.token = None
        
        if self.username and self.password and len(self.username)>0 and len(self.password)>0:
            self.logout()
            util.info('[SC] Login user=%s, pass=*****' % self.username)
            
            try:
                # get salt
                headers,req = self._create_request('',{'username_or_email':self.username})
                data = post(self._url('api/salt/'),req,headers=headers)
                xml = ET.fromstring(data)
                if not xml.find('status').text == 'OK':
                    util.error('[SC] Server returned error status, response: %s' % data)
                    return False
                salt = xml.find('salt').text
                # create hashes
                password = hashlib.sha1(md5crypt(self.password.encode('utf-8'), salt.encode('utf-8'))).hexdigest()
                digest = hashlib.md5(self.username + ':Webshare:' + self.password).hexdigest()
                # login
                headers,req = self._create_request('',{'username_or_email':self.username,'password':password,'digest':digest,'keep_logged_in':1})
                data = post(self._url('api/login/'),req,headers=headers)
                xml = ET.fromstring(data)
                if not xml.find('status').text == 'OK':
                    self.clearToken()
                    util.error('[SC] Server returned error status, response: %s' % data)
                    return False
                self.saveToken(xml.find('token').text)
                try:
                    util.cache_cookies(None)
                except:
                    pass
                util.info('[SC] Login successfull')
                return True
            except Exception, e:
                util.info('[SC] Login error %s' % str(e))
        self.clearToken()
        return False

    def userData(self, all=False):
        if self.token is not None:
            headers,req = self._create_request('/',{'wst':self.token})
            try:
                util.info('[SC] userData')
                data = post(self._url('api/user_data/'), req, headers=headers)
            except:
                self.clearToken()
                return False
            util.info('[SC] userdata dat: %s' % data)
            xml = ET.fromstring(data)
            if not xml.find('status').text == 'OK':
                self.clearToken()
                return False
            if all == True:
                return xml
            util.debug("[SC] userInfo: %s %s" % (xml.find('ident').text, xml.find('vip').text))
            if xml.find('vip').text == '1':
                xbmcgui.Window(10000).setProperty('ws.vip', '1')
                xbmcgui.Window(10000).setProperty('ws.ident', xml.find('ident').text)
                xbmcgui.Window(10000).setProperty('ws.days', xml.find('vip_days').text)
                return int(xml.find('vip_days').text)
            else:
                xbmcgui.Window(10000).setProperty('ws.vip', '0')
                
        return False
    
    def logout(self):
        util.info("[SC] logout")
        headers,req = self._create_request('/',{'wst':self.token})
        try:
            self.clearToken()
            post(self._url('api/logout/'), req, headers=headers)
            util.cache_cookies(None)
        except:
            util.debug("[SC] chyba logout")
            pass

    def clearToken(self):
        if self.cache is not None:
            self.cache.set('ws.token', None)
        self.win.clearProperty('ws.token')
        self.token = None
        pass
    
    def getToken(self):
        try:
            if self.cache is None:
                self.w = xbmcgui.Window(10000)
                token = self.w.getProperty('ws.token')
            else:
                token = self.cache.get('ws.token')

            if token is not None and token != '':
                self.token = token
            else:
                self.token = None
        except:
            util.info('[SC] token ERR %s' % str(traceback.format_exc()))
            self.token = None
    
    def saveToken(self, token):
        self.token = str(token)
        if self.cache is not None:
            ttl = timedelta(days=7)
            self.cache.set('ws.token', self.token, expiration=ttl)
        self.win.setProperty('ws.token', self.token)
        pass
    
    def resolve(self,ident):
        headers,req = self._create_request('/',{'ident':ident,'wst':self.token})
        util.info(headers)
        util.info(req)
        try:
            data = post(self._url('api/file_link/'), req, headers=headers)
            xml = ET.fromstring(data)
            if not xml.find('status').text == 'OK':
                self.win.clearProperty('ws.token')
                self.token = None
                util.error('[SC] Server returned error status, response: %s' % data)
                raise ResolveException(xml.find('message').text)
            return xml.find('link').text
        except Exception, e:
            raise ResolveException(e)
