import requests
import time
import datetime
import random

from logger import logger as Logger

class SlackError(Exception):
    def __init__(self, message):
        self.message = message
    
class SlackTooManyRequestsError(Exception):
    def __init__(self, message):
        self.message = message
    
class SlackClient(object):
    BASE_URL = 'https://slack.com'
    RATE_LIMIT = 1
    QUEUE = []
    
    def __init__(self, file, authorization, token, verify=False):
        requests.packages.urllib3.disable_warnings()
        self.properties = {}
        with open("keys/" + file + ".properties", 'r') as inFile:
            for line in inFile:
                propertyLine = line.split('=')
                self.properties[propertyLine[0]] = propertyLine[1].rstrip()

        self.verify = verify
        self.blocked_until = None
        self.channel_name_id_map = {}
    
        self.channel = self.channel_name_to_id(self.properties['default.channel'][1:])
        
        if(authorization is not None):
            # RTM -- # https://slack.com/oauth/authorize?client_id=182473328642.336524346324&response_type=code&redirect_uri=http://localhost&scope=bot
            params = {'client_id': self.properties['client.id'], 'client_secret': self.properties['client.secret'], 'code': authorization, 'redirect_uri': 'http://localhost'}
            rtmResponse = self._make_api_request("oauth.access", True, params)
            self.botAccessToken = rtmResponse.json()['bot_access_token']
        
        if(token is not None):
            self.botAccessToken = token

## {'ok': True, 'access_token': 'xoxp-182473328642-268056090199-535906645510-5b1c8c783d9f478e5b02b580da81c872', 'scope': 'identify,bot,channels:history,channels:read,team:read,channels:write', 'user_id': 'U7W1N2N5V', 'team_name': 'Coffee and Code', 'team_id': 'T5CDX9NJW', 'bot': {'bot_user_id': 'UFRG3R4B1', 'bot_access_token': 'xoxb-182473328642-535547854375-eubwk7Rz5Ev48Qv8aGaWLg6M'}}
        params = {'token': self.botAccessToken}
        rtmConnect = self._make_api_request("rtm.connect", False, params)
        self.webSocketUrl = rtmConnect.json()['url']
        
    def getWebSocketUrl(self):
        return self.webSocketUrl

    def _make_auth_request(self, as_user, params):
        url = SlackClient.BASE_URL + "/oauth/authorize?client_id=" + self.properties['client.id'] + "&response_type=code&scope=bot&redirect_uri=http://localhost"
        response = requests.get(url)
        
    def _make_api_request(self, method, as_user, params):
        return self._make_request(method, SlackClient.BASE_URL + "/api", as_user, params)
        
    def _make_request(self, method, baseUrl, as_user, params):
        if(self.blocked_until is not None and datetime.datetime.utcnow() < self.blocked_until):
            sleepTime = (self.blocked_until - datetime.datetime.utcnow()).total_seconds()
            Logger.log("RATELIMIT", "Sleeping for {0} seconds to maintain rate limit of {1}".format(str(sleepTime), str(SlackClient.RATE_LIMIT)))
            time.sleep(sleepTime)
            # raise SlackTooManyRequestsError("Too many requests - wait until {0}".format(self.blocked_until))
    
        url = "%s/%s" % (baseUrl, method)
        if(as_user):
            params['token'] = self.properties['access.token']
        else:
            params['token'] = self.properties['bot.access.token']
        response = requests.post(url, data=params, verify=self.verify)
        self.blocked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=(1 / SlackClient.RATE_LIMIT))
        
        if(response.status_code == 429):
            retry_after = int(response.headers.get('retry-after', '1'))
            self.blocked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=retry_after)
            raise SlackTooManyRequestsError("Too many requests - wait until {0}".format(self.blocked_until))
        
        try:
            result = response.json()
            if not result['ok']:
                Logger.log("RESPONSE_NOT_OK", str(result))
                Logger.log("RESPONSE_NOT_OK", str(result['error']))
        except:
            Logger.log("JSON_PARSE_EXCEPTION", str(response.status_code))
            Logger.log(params, str(response))
        
        return response
        
    def channels_list(self, cursor=None, exclude_archived=True, **params):
        method = 'conversations.list'
        params.update({
                'exclude_archived': exclude_archived and 1 or 0,
                'limit': 1000,
                'types': "public_channel"})
        if(cursor is not None):
            params.update({'cursor': cursor})
        return self._make_api_request(method, True, params)
        
    def channels_info(self, channel, **params):
        method = 'channels.info`'
        params.update({'channel': channel})
        return self._make_api_request(method, True, params)
        
    def channel_name_to_id(self, channel_name, force_lookup=False):
        if(force_lookup or not self.channel_name_id_map):
            cursor = None
            while(cursor != ''):
                channelsResponse = self.channels_list(cursor = cursor)
                channels = channelsResponse.json()['channels']
                for channel in channels:
                    self.channel_name_id_map[channel['name']] = channel['id']                
                cursor = channelsResponse.json()['response_metadata']['next_cursor']
                
        channel = channel_name.startswith('#') and channel_name[1:] or channel_name
        Logger.log("CHANNEL", channel)
        return self.channel_name_id_map.get(channel)
    
    def get_channel_map(self):
        return self.channel_name_id_map
        
    def chat_read(self, ts, **params):
        method = 'channels.history'
        params.update({
            'channel': self.channel
        })
        if(ts is not None):
            params.update({
                'oldest': ts
            })
        return self._make_api_request(method, True, params)
    
    def chat_post_message(self, text, **params):
        images = self.properties['bot.avatar'].split(",")
        image = random.choice(images)
        
        return self.chat_post_message_customImage(text, image, **params)
    
    def chat_post_message_customImage(self, text, image, **params):
        method = 'chat.postMessage'
        params.update({
            'channel': self.channel,
            'text': ">>>" + text,
            'icon_url': image,
            'as_user': False
        })
        return self._make_api_request(method, False, params)
    
    def chat_delete_message(self, ts, **params):
        method = 'chat.delete'
        params.update({
            'channel': self.channel,
            'ts': ts
        })
        return self._make_api_request(method, False, params)
    
    def get_bot_info(self, **params):
        method = 'bots.info'
        params.update({
            'bot': self.properties['bot.id']
        })
        return self._make_api_request(method, False, params)
    
    def changeChannel(self, channel):
        if channel.startswith('<'):
            self.channel = channel.split("|")[0][2:]
        Logger.log("Channel Change", str(self.channel))