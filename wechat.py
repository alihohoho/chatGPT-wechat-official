import json
import hashlib
import threading
import configparser
from urllib import parse
import xml.etree.ElementTree as ET

from revChatGPT.revChatGPT import Chatbot

from util import getLogger, head, make_request

logger = getLogger("wechat")

config = configparser.ConfigParser()
config.read("config.ini")
wechat = config["wechat"]
chatGPT = config["chatGPT"]


config = {
    "email": chatGPT["Email"],
    "password": chatGPT["Password"],
    "session_token": chatGPT["SessionToken"],
}
try:
    chatbot = Chatbot(config, conversation_id=None)
except Exception as e:
    logger.error(e)
    raise ValueError(e)


class WXRequest:
    BASE_URL = "https://api.weixin.qq.com/cgi-bin"

    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super(WXRequest, cls).__new__(cls)
        return cls._instance

    def __init__(self, appid=wechat["Appid"], secret=wechat["Secret"]) -> None:
        try:
            self.__checkKey(appid, secret)
            self.appid = appid
            self.secret = secret
        except ValueError as e:
            logger.info(e)

    def sendCustomMessage(self, user, content):
        url = f"{self.BASE_URL}/message/custom/send?access_token={self.__token}"
        data = {
            "touser": user,
            "msgtype": "text",
            "text": {"content": content},
        }
        data = json.dumps(data, ensure_ascii=False).encode()
        make_request(url, method="POST", data=data)

    @property
    def __token(self):
        query = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.secret,
        }
        url = f"{self.BASE_URL}/token?{parse.urlencode(query)}"
        data = make_request(url, method="GET")
        return data.get("access_token")

    @staticmethod
    def __checkKey(appid, secret):
        if not (appid and secret):
            raise ValueError("WeixinAuthSign: Invalid key")


class Bot:
    def __init__(self, salt=wechat["Salt"]) -> None:
        self.salt = salt

    @staticmethod
    def sendChatGPTMessage(input, user):
        try:
            response = chatbot.get_chat_response(input, output="text")
            result = response.get("message")
        except Exception as e:
            result = "呀，不晓得说什么，请再给个机会"
            logger.error(e)
        wxReq = WXRequest()
        wxReq.sendCustomMessage(user, result)

    @staticmethod
    def receive(data):
        root = ET.fromstring(data)
        info_from_user = {}
        for child in root:
            info_from_user[child.tag] = child.text

        MsgType = info_from_user.get("MsgType")
        FromUserName = info_from_user.get("FromUserName")
        ToUserName = info_from_user.get("ToUserName")
        Content = info_from_user.get("Content")
        if MsgType == "text" and Content:
            task = lambda: Bot.sendChatGPTMessage(Content, FromUserName)
            chatThread = threading.Thread(target=task, name="chatThread")
            chatThread.start()
            return Bot.gen_response(FromUserName, ToUserName, "阿铁正在组织语言(10s+)...")
        return "success"

    @staticmethod
    def gen_response(from_user, to_user, content):
        return (
            "<xml>"
            f"<ToUserName><![CDATA[{from_user}]]>"
            f"</ToUserName><FromUserName><![CDATA[{to_user}]]>"
            "</FromUserName><CreateTime>{int(time.time())}</CreateTime>"
            "<MsgType><![CDATA[text]]></MsgType>"
            f"<Content><![CDATA[{content}]]></Content>"
            "</xml>"
        )

    def check_token(self, data):
        signature = head(data.get("signature"))
        timestamp = head(data.get("timestamp"))
        nonce = head(data.get("nonce"))
        echostr = head(data.get("echostr"))

        sha1 = hashlib.sha1()
        for param in [nonce, timestamp, self.salt]:
            sha1.update(param.encode("utf-8"))
        hashcode = sha1.hexdigest()
        if hashcode == signature:
            return echostr
        raise "Auth Fail"


if __name__ == "__main__":
    wxReq = WXRequest()
    wxReq.sendCustomMessage("oYxHq6ePss-oElUbt7jZ6LAcsI9w", "hello")
