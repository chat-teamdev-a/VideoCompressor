import socket
import os
import json


class Server:
    stream_rate = 4096

    # ファイルアップロード時のヘッダー構造
    file_upload_header_size = 36
    file_upload_byterange_filename = 1
    file_upload_byterange_json = 4
    file_upload_byterange_filesize = 36

    # ファイル編集時のヘッダー構造
    file_edit_header_size = 64
    file_edit_byterange_json = 16
    file_edit_byterange_media_type = 17
    file_edit_byterange_payload = 64

    def __init__(self, ip_address, port, path_name):
        self.address = (ip_address, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # アップロードされるファイルの保存場所の設定
        self.create_video_path(path_name)
        # ソケットのバインド
        self.sock.bind(self.address)
        # リッスン
        self.sock.listen(1)


    def create_video_path(self, path):
        self.video_path = path.encode('utf-8')
        if not os.path.exists(self.video_path):
            os.makedirs(self.video_path)

    # 取り敢えずアップロードだけ受け付ける
    def listen_receive_file(self):
        while True:
            # リクエストを受け入れ
            client_sock, client_address = self.sock.accept()
            try:
                print('connection from', client_address)
                header = client_sock.recv(self.file_upload_header_size)

                filename_length = int.from_bytes(header[: self.file_upload_byterange_filename], 'big')
                json_length = int.from_bytes(header[self.file_upload_byterange_filename: self.file_upload_byterange_json], 'big')
                data_length = int.from_bytes(header[self.file_upload_byterange_json: self.file_upload_byterange_filesize], 'big')
                # リクエスト内のデータをwhileでstream_rate分ずつ用意した新規ファイルに書き込ぬ
                print(f'Received header from client. data_length: {data_length}, filename_length: {filename_length}, json_length: {json_length}')

                if data_length == 0:
                    raise Exception('No data to read from client.')

                filename = client_sock.recv(filename_length)
                # jsonデータは取りあえず不要
                _ = client_sock.recv(json_length)

                # アップロードされたデータをリクエスト内のファイル名でサーバ側で用意したフォルダ内に保存
                with open(os.path.join(self.video_path, filename), 'wb+') as f:
                    # data_lengthが0になるまでクライアントからデータをsteram_rateずつ書き込んでいく
                    # このループ中にクライアント側からデータ送信の中断があった時...
                    while data_length > 0:
                        data = client_sock.recv(self.stream_rate if self.stream_rate <= data_length else data_length)
                        if len(data) == 0:
                            raise Exception('Connection closed by client')
                        f.write(data)
                        data_length -= len(data)

                print('Downloading finished')

                # アップロードが完了したことをレスポンスするために、ステータスメッセージを含めたデータをディクショナリとしてJSONデータに格納する
                jsondata = json.dumps({'status': 'SUCCESS'})
                jsondata_byte = jsondata.encode('utf-8')
                header = Server.file_upload_protocol_header(len(filename), len(jsondata_byte))
                client_sock.send(header)
                client_sock.send(filename)
                client_sock.send(jsondata_byte)

            # 何らかのエラーが発生した場合にerrをメッセージとしてクライアントソケットを閉じる
            except Exception as err:
                Server.close_client_socket_with_error(client_sock, err)
            finally:
                print("Closing current connection")
                client_sock.close()


    @staticmethod
    def close_client_socket_with_error(client_sock, err):
        print(f'Error: {err}')
        print('Current Client Socket Close...')
        client_sock.close()


    @staticmethod
    def file_upload_protocol_header(filename_length, json_length):
        return filename_length.to_bytes(1, 'big') + json_length.to_bytes(3, 'big')



if __name__ == '__main__':
    # ソケットの作成
    address = '0.0.0.0'
    port = 9001
    sock = Server(address, port, 'client_videos')

    # ファイルアップロードの待機
    sock.listen_receive_file()
