import socket
import sys
import os
import json

class Client:
    server_address = ''
    server_port = 9001
    stream_rate = 4096
    header_size_response_upload_completed = 4

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
    def protocol_header_file_upload(filename_length, json_length, data_length):
        return filename_length.to_bytes(1, 'big') + json_length.to_bytes(3, 'big') + data_length.to_bytes(32, 'big')


    @staticmethod
    def file_validation(file_size, file_name):
        # ファイルサイズのバリデーション
        if file_size > pow(2, 32):
            return 'File must be below 2GB'
        # ファイル名からフォーマットバリデーションを行う
        if not file_name.endswith('.mp4'):
            return 'File format must be mp4'
        
        return None


    def close_socket_with_error(self, err):
        print(f'Error: {err}')
        print('Socket Close...')
        self.sock.close()
        sys.exit(1)


    def upload_file(self):
        try:
            filepath = input('Type in a file to upload: ')

            with open(filepath, 'rb') as f:
                f.seek(0, os.SEEK_END)
                file_size = f.tell()
                f.seek(0, 0)
                file_name = os.path.basename(f.name)

                err = Client.file_validation(file_size, file_name)
                if err != None:
                    self.close_socket_with_error(err)
                
                filename_bits = file_name.encode('utf-8')

                # ヘッダーの作成
                header = Client.protocol_header_file_upload(len(filename_bits), 0, file_size)
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
        # 圧縮
        if num == 1:
            print("Hello")
        # 編集終了→ソケットを閉じる
        if num == 6:
            print('Done your editting...')
            self.sock.close()
            sys.exit(1)


    def edit_file(self):
        # クライアントが6番を押したりcmd+cとか強制終了するまでループする
        # ここでクライアントが適した数字を一定時間打たなかったらサーバがわで打ち切られて終了する
        while True:
            # どの機能を適用したいのかを番号で選ぶ→1~5, 6は編集終了
            feature_input = input('Which features do you want to apply?: ')

            if not feature_input.isdigit() or int(feature_input) < 0 or int(feature_input) > 6:
                print('Type a number within 0~6')
                continue

            feature_num = int(feature_input)

            # サーバーに特定の機能のリクエストを投げる関数
            self.edit_feature_handle(feature_num)


if __name__ == '__main__':
    client = Client()