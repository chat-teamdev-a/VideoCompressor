# 最初にサーバに送信される 32 バイトは、ファイルのバイト数をサーバに通知します
# アップロードしようとしているファイルのfilesizeがオーバーした時のraiseはクライアント側でおこなう
# アップロードしようとしているファイルがmp4であるかどうかのフォーマットバリデーションはクライアント側で行う
import socket
import sys
import os
import json

# テスト動画のパス：/Users/reirei/Desktop/work/Programming/Recursion/teamChatMessanger/myVideo.mp4

def protocol_header(filename_length, json_length, data_length):
    return filename_length.to_bytes(1, 'big') + json_length.to_bytes(3, 'big') + data_length.to_bytes(32, 'big')


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_address = ''
server_port = 9001
stream_rate = 4096
header_size = 4
try:
    sock.connect((server_address, server_port))
except socket.error as err:
    print(err)
    sys.exit(1)

try:
    filepath = input('Type in a file to upload: ')

    with open(filepath, 'rb') as f:
        f.seek(0, os.SEEK_END)
        filesize = f.tell()
        f.seek(0, 0)

        # ファイルサイズのバリデーション
        if filesize > pow(2, 32):
            raise Exception('File must be below 2GB')
        filename = os.path.basename(f.name)
        # ファイル名からフォーマットバリデーションを行う
        if not filename.endswith('.mp4'):
            raise Exception('File format must be mp4')
        
        filename_bits = filename.encode('utf-8')

        # ヘッダーの作成
        header = protocol_header(len(filename_bits), 0, filesize)
        # ヘッダーの送信
        sock.send(header)
        # ファイル名の送信
        sock.send(filename_bits)
        # JSONデータ(今は空)の送信
        sock.send(b'')
        # stream_rateずつ読み出しながら送信
        data = f.read(stream_rate)
        while data:
            sock.send(data)
            data = f.read(stream_rate)
        
        # アップロードが正常に完了したレスポンスを受け取る
        response_header = sock.recv(header_size)
        filename_length = response_header[0]
        json_length = int.from_bytes(response_header[1:], 'big')

        _ = sock.recv(filename_length)
        response_status_json = sock.recv(json_length).decode()
        response_status = json.loads(response_status_json)
        
        print(f"Status: {response_status['status']}")

finally:
    print('Closing socket')
    sock.close()
