import socket
import os
import json
# ヘッダーの内容は、ファイル名、jsonデータ、メインデータの３種類が含まれていればいいか？
def protocol_header(filename_length, json_length):
    return filename_length.to_bytes(1, 'big') + json_length.to_bytes(3, 'big')



# ソケットの作成
address = '0.0.0.0'
port = 9001
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# フォルダの作成
video_path = b'client_videos'
if not os.path.exists(video_path):
    os.makedirs(video_path)

# ソケットのバインド
sock.bind((address, port))
# リッスン
sock.listen(1)

header_size = 36
byterange_filename = 1
byterange_json = 4
# ファイルデータは残りのバイト数
byterange_filesize = 36
stream_rate = 4096

while True:
    # リクエストを受け入れ
    client_sock, client_address = sock.accept()
    try:
        print('connection from', client_address)
        header = client_sock.recv(header_size)

        filename_length = int.from_bytes(header[: byterange_filename], 'big')
        json_length = int.from_bytes(header[byterange_filename: byterange_json], 'big')
        data_length = int.from_bytes(header[byterange_json: byterange_filesize], 'big')
        # リクエスト内のデータをwhileでstream_rate分ずつ用意した新規ファイルに書き込ぬ
        print(f'Received header from client. data_length: {data_length}, filename_length: {filename_length}, json_length: {json_length}')

        if data_length == 0:
            raise Exception('No data to read from client.')

        filename = client_sock.recv(filename_length)
        # jsonデータは取りあえず不要
        _ = client_sock.recv(json_length)

        # アップロードされたデータをリクエスト内のファイル名でサーバ側で用意したフォルダ内に保存
        with open(os.path.join(video_path, filename), 'wb+') as f:
            # data_lengthが0になるまでクライアントからデータをsteram_rateずつ書き込んでいく
            while data_length > 0:
                data = client_sock.recv(stream_rate if stream_rate <= data_length else data_length)
                f.write(data)
                data_length -= len(data)

        print('Downloading finished')

        # アップロードが完了したことをレスポンスするために、ステータスメッセージを含めたデータをディクショナリとしてJSONデータに格納する
        jsondata = json.dumps({'status': 'SUCCESS'})
        jsondata_byte = jsondata.encode('utf-8')
        header = protocol_header(len(filename), len(jsondata_byte))
        client_sock.send(header)
        client_sock.send(filename)
        client_sock.send(jsondata_byte)


    except Exception as e:
        print('Error: ' + str(e))
    finally:
        print("Closing current connection")
        client_sock.close()

