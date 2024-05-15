# 勘違いしていること
# 通信の際にメディアタイプというのがあるが、これはフォーマットのバリデーション(エラーハンドリング)のために使うのではない
# 単にサーバ側でそのメディアタイプによって、ペイロードの処理の方法をどのようにするのかを条件分けするために使うのだ！
# なので、クライアント側・サーバ側それぞれで何か問題のあるようなデータを送信した時のエラー内容は、その間違ったデータを送った方でエラーハンドリングをするようにしないとマジでめんどいことになる

# エラーハンドリングは優先度２位。１位は編集機能が最後までできるかどうか

import socket
import sys
import os
import json
from util import Util

class Client:
    server_address = ''
    server_port = 9001
    stream_rate = 4096
    header_size_response_upload_completed = 4
    # ファイル編集時のボディ構造
    file_edit_header_size = 64
    file_edit_byterange_json = 16
    file_edit_byterange_media_type = 17
    file_edit_byterange_payload = 64


    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 接続
        try:
            self.sock.connect((self.server_address, self.server_port))
        except socket.error as err:
            print(err)
            sys.exit(1)
        
        self.upload_file()
        # edit_fileが実行される時にはserver側ではアップロードされたファイルを保存して待機している
        # →どのような状況になっても、クライアントはサーバーにリクエストを返さなければ、サーバは動画を削除することができない
        self.edit_file()


    @staticmethod
    def file_upload_protocol_header(filename_length, json_length, data_length):
        return filename_length.to_bytes(1, 'big') + json_length.to_bytes(3, 'big') + data_length.to_bytes(32, 'big')


    @staticmethod
    def file_edit_protocol_header(json_length, media_type_length, data_length):
        return json_length.to_bytes(16, 'big') + media_type_length.to_bytes(1, 'big') +  data_length.to_bytes(47, 'big')


    def close_socket_with_error(self, err):
        print(f'Error: {err}')
        print('Socket Close...')
        self.sock.close()
        sys.exit(1)


    def file_edit_handle_tcp(self, json_data_byte, media_type_num, payload = None):
        try:
            media_type_num_byte = media_type_num.to_bytes(1, 'big')
            # ペイロードは空
            # ヘッダーの作成
            header = Client.file_edit_protocol_header(len(json_data_byte), len(media_type_num_byte), 0)
            self.sock.send(header)
            self.sock.send(json_data_byte)
            self.sock.send(media_type_num_byte)
            self.sock.send(b'')
            
        except Exception as err:
            self.close_socket_with_error(err)


    def upload_file(self):
        try:
            # テスト用ではフォルダmy_videosにあるテスト用動画素材を使用する
            # filepath = input('Type in a file to upload: ')
            filepath = './my_videos/nature.mp4'
            with open(filepath, 'rb') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                f.seek(0, 0)
                file_name = os.path.basename(f.name)

                err = Util.file_validation(file_size, file_name)
                if err != None:
                    raise Exception(err)
                
                filename_bits = file_name.encode('utf-8')

                # ヘッダーの作成
                header = Client.file_upload_protocol_header(len(filename_bits), 0, file_size)
                # ヘッダーの送信
                self.sock.send(header)
                # ファイル名の送信
                self.sock.send(filename_bits)
                # JSONデータ(今は空)の送信
                self.sock.send(b'')
                # stream_rateずつ読み出しながら送信
                data = f.read(self.stream_rate)
                while data:
                    self.sock.send(data)
                    data = f.read(self.stream_rate)
                
                # アップロードが正常に完了したレスポンスを受け取る
                response_header = self.sock.recv(self.header_size_response_upload_completed)
                filename_length = response_header[0]
                json_length = int.from_bytes(response_header[1:], 'big')

                _ = self.sock.recv(filename_length)
                response_status_json = self.sock.recv(json_length).decode()
                response_status = json.loads(response_status_json)
                
                print(f"Status: {response_status['status']}")

        except Exception as err:
            self.close_socket_with_error(err)


    def edit_feature_handle(self, num):
        # 編集終了
        if num == 6:
            print('Done your editting...')
            self.sock.close()
            sys.exit(1)
        # 特定の編集処理を行う TODO edit用のヘッダー・ボディの作成から送信までを1つの関数にする
        else:
            required_info_for_edit = {'feature_num': num}
            json_data = json.dumps(required_info_for_edit)
            json_data_byte = json_data.encode('utf-8')
            # media_type_lenghtは取り敢えず今回使用するmp4を0と見做して使用する
            media_type_num = 0
            media_type_num_byte = media_type_num.to_bytes(1, 'big')
            # ペイロードは空
            # ヘッダーの作成
            header = Client.file_edit_protocol_header(len(json_data_byte), len(media_type_num_byte), 0)
            self.sock.send(header)
            self.sock.send(json_data_byte)
            self.sock.send(media_type_num_byte)
            self.sock.send(b'')

            print('Edit request sent successfully!')


    # 編集が完了したファイルを受け取るために、サーバからヘッダ・ボディを受け取る
    def handle_response(self, output_file_name):
        try:
            header = self.sock.recv(self.file_edit_header_size)
            
            json_length = int.from_bytes(header[:self.file_edit_byterange_json], 'big')
            media_type_length = int.from_bytes(header[self.file_edit_byterange_json: self.file_edit_byterange_media_type], 'big')
            data_length = int.from_bytes(header[self.file_edit_byterange_media_type: self.file_edit_byterange_payload], 'big')
            # リクエスト内のデータをwhileでstream_rate分ずつ用意した新規ファイルに書き込ぬ
            print(f'Received header from Server. json_length: {json_length}, media_type_length: {media_type_length}, data_length: {data_length}')

            if data_length == 0:
                raise Exception('No data to read from server.')

            # jsonデータは取りあえず不要
            _ = self.sock.recv(json_length)

            # サーバから送られてきたデータをアウトプットファイル名でフォルダ内に保存
            with open(os.path.join(self.video_path, output_file_name), 'wb+') as f:
                # data_lengthが0になるまでサーバからデータをsteram_rateずつ書き込んでいく
                # このループ中にサーバ側からデータ送信の中断があった時...
                while data_length > 0:
                    data = self.sock.recv(self.stream_rate if self.stream_rate <= data_length else data_length)
                    if len(data) == 0:
                        raise Exception('Connection closed by server')
                    f.write(data)
                    data_length -= len(data)
            
        # サーバからファイル受信中に何らかのエラーが発生したので、それをクライアント上のみならずサーバ上にも知らせるためにエラー内容を含めたTCP通信を行なってあげる
        except Exception as err:
            error_data = {'error': err}
            json_data = json.dumps(error_data)
            self.file_edit_handle_tcp(json_data.encode('utf-8'), -1)


    def edit_file(self):
        # クライアントが6番を押したりcmd+cとか強制終了するまでループする
        # ここでクライアントが適した数字を一定時間打たなかったらサーバがわで打ち切られて終了する
        try:
            while True:
                # どの機能を適用したいのかを番号で選ぶ→1~5, 6は編集終了
                feature_input = input('Which features do you want to apply?: ')

                if not feature_input.isdigit() or int(feature_input) < 0 or int(feature_input) > 6:
                    print('Type a number within 0~6')
                    continue

                output_file_name = input('Output file name: ')
                
                feature_num = int(feature_input)

                # サーバーに特定の機能のリクエストを投げる関数
                self.edit_feature_handle(feature_num)
                # 編集完了したサーバからヘッダー及びstream_rateずつ小分けにして送信される
                self.handle_response(output_file_name)

        except Exception as err:
            self.close_socket_with_error(err)



if __name__ == '__main__':
    client = Client()