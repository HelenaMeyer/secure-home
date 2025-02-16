#!/usr/bin/env python

# Copyright (C) 2020 Toitware ApS. All rights reserved.

import multiprocessing
import os
import signal
import socket
import sys

import grpc
from toit.api import auth_pb2, auth_pb2_grpc
from toit.api.pubsub import (publish_pb2, publish_pb2_grpc, subscribe_pb2,
                             subscribe_pb2_grpc)

INCOMING_TOPIC = "cloud:door/out"
OUTGOING_TOPIC = "cloud:door/in"


def create_channel(access_token=None):
  credentials = grpc.ssl_channel_credentials()
  if access_token is not None:
      credentials = grpc.composite_channel_credentials(credentials,
          grpc.access_token_call_credentials(access_token))

  return grpc.secure_channel("api.toit.io:443", credentials)

def create_subscription(subscription):
    return subscribe_pb2.Subscription(name=subscription,topic=INCOMING_TOPIC)

def setup_channel(username, password):
  channel = create_channel()
  try:
      auth = auth_pb2_grpc.AuthStub(channel)
      resp = auth.Login(auth_pb2.LoginRequest(username=username,password=password))
      return create_channel(access_token=str(resp.access_token, 'utf-8'))
  finally:
      channel.close()

def get_messages(channel, subscription):
    while True:
        sub_stub = subscribe_pb2_grpc.SubscribeStub(channel)
        stream = sub_stub.Stream(subscribe_pb2.StreamRequest(subscription=subscription))

        try:
            for d in stream:
                for message in d.messages:
                    yield message
        except grpc.RpcError as rpc_error:
            if rpc_error.code() == grpc.StatusCode.UNAUTHENTICATED:
                raise rpc_error

def ack_message(channel, subscription, item):
    sub_stub = subscribe_pb2_grpc.SubscribeStub(channel)
    sub_stub.Acknowledge(subscribe_pb2.AcknowledgeRequest(subscription=subscription,envelope_ids=[item.id]))

def publish_message(channel, msg):
    pub_stub = publish_pb2_grpc.PublishStub(channel)
    pub_stub.Publish(publish_pb2.PublishRequest(topic=OUTGOING_TOPIC,publisher_name=socket.gethostname(),data=[msg.encode("utf-8")]))

class Subscribe(multiprocessing.Process):
    def __init__(self, username, password, subscription):
        multiprocessing.Process.__init__(self)
        self.exit = multiprocessing.Event()
        self.username = username
        self.password = password
        self.subscription = create_subscription(subscription)

    def run(self):
        channel = setup_channel(self.username, self.password)
        try:
            while True:
                try:
                    for msg in get_messages(channel, self.subscription):
                        print("received: '"+ msg.message.data.decode("utf-8") + "'")
                        ack_message(channel, self.subscription, msg)
                except grpc.RpcError as rpc_error:
                    if rpc_error.code() == grpc.StatusCode.UNAUTHENTICATED:
                        self.channel = setup_channel(self.username, self.password)
                    else:
                        raise rpc_error
        except KeyboardInterrupt:
            pass
        finally:
            channel.close()

def main():
    username = sys.argv[1]
    password = sys.argv[2]
    subscription = sys.argv[3]

    original_sigint_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGINT, original_sigint_handler)

    subscribeProcess = Subscribe(username=username, password=password, subscription=subscription)
    subscribeProcess.start()

    channel = setup_channel(username, password)
    try:
        print("Write a message to send:")
        while True:
            line = sys.stdin.readline().strip()
            print("sending: '" + line+ "'")
            publish_message(channel, line)
    except KeyboardInterrupt:
        pass
    finally:
        subscribeProcess.terminate()
        subscribeProcess.join()
        channel.close()
if __name__ == '__main__':
    main()
