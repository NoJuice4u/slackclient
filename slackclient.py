import requests
import datetime
import random

class SlackError(Exception):
    pass
    
class SlackClient(object):
    BASE_URL = 'https://slack.com/api'
    
    def __init__(self, file, verify=False):
        self.properties = {}
        with open("keys/" + file + ".properties", 'r') as inFile:
            for line in inFile:
                propertyLine = line.split('=')
                self.properties[propertyLine[0]] = propertyLine[1].rstrip()

        self.verify = verify
        self.blocked_until = None
        self.channel_name_id_map = {}
    
        self.channel = self.channel_name_to_id(self.properties['default.channel'][1:])

        requests.packages.urllib3.disable_warnings()

    def _make_request(self, method, as_user, params):
        if(self.blocked_until is not None and datetime.datetime.utcnow() < self.blocked_until):
            raise SlackError("Too many requests - wait until {0}".format(self.blocked_until))
    
        url = "%s/%s" % (SlackClient.BASE_URL, method)
        if(as_user):
            params['token'] = self.properties['access.token']
        else:
            params['token'] = self.properties['bot.access.token']
        response = requests.post(url, data=params, verify=self.verify)
        
        if(response.status_code == 429):
            retry_after = int(response.headers.get('retry-after', '1'))
            self.blocked_until = datetime.datetime.utcnow() + datetime.timedelta(seconds=retry_after)
            raise SlackError("Too many requests - retry after {0} second(s)".format(retry_after))
            
        try:
            result = response.json()
            if not result['ok']:
                print(result)
                print("ERROR: " + str(result['error']))
        except:
            print("JSON Parse Exception!  Send message to Slack may have failed!")
            print(response.status_code)
            print(params)
            print(response)
        
        return response
        
    def channels_list(self, cursor=None, exclude_archived=True, **params):
        method = 'conversations.list'
        params.update({
                'exclude_archived': exclude_archived and 1 or 0,
                'limit': 1000,
                'types': "public_channel"})
        if(cursor is not None):
            params.update({'cursor': cursor})
        print(params)
        return self._make_request(method, True, params)
        
    def channels_info(self, channel, **params):
        method = 'channels.info`'
        params.update({'channel': channel})
        return self._make_request(method, True, params)
        
    def channel_name_to_id(self, channel_name, force_lookup=False):
        if(force_lookup or not self.channel_name_id_map):
            cursor = None
            while(cursor != ''):
                channelsResponse = self.channels_list(cursor = cursor)
                channels = channelsResponse.json()['channels']
                for channel in channels:
                    self.channel_name_id_map[channel['name']] = channel['id']                
                cursor = channelsResponse.json()['response_metadata']['next_cursor']
                print(cursor)
                
        channel = channel_name.startswith('#') and channel_name[1:] or channel_name
        print("SET Channel: " + channel)
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
        return self._make_request(method, True, params)
    
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
        return self._make_request(method, False, params)
    
    def chat_delete_message(self, ts, **params):
        method = 'chat.delete'
        params.update({
            'channel': self.channel,
            'ts': ts
        })
        return self._make_request(method, False, params)
    
    def get_bot_info(self, **params):
        method = 'bots.info'
        params.update({
            'bot': self.properties['bot.id']
        })
        return self._make_request(method, False, params)
    
    def changeChannel(self, channel):
        if channel.startswith('<'):
            print(channel.split("|")[0][2:])
            self.channel = channel.split("|")[0][2:]
        print("Channel Change: " + str(self.channel))

#client = SlackClient()
#channel = '#bot_sandbox'

#chatResponse = client.chat_read(channel, None).json()

# BFRG3R495

#if(True == False):
#    for item in chatResponse['messages'] :
#        print(item['ts'])
#        if('bot_id' in item and item['bot_id'] == "BFRG3R495"):
#            client.chat_delete_message(channel, item['ts'])

#print(" ")

#for item in chatResponse['messages'] :
#    print(item)
    
#chatResponse = client.get_bot_info()
#print(chatResponse.text)
# client.chat_post_message(channel, "Testing, Testing, 1 2 3!", username="Launch Bot")