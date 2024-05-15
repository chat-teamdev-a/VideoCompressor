
# メディアタイプは-1、ペイロードは空、JSONデータにエラー内容('error message')と解決策('solution')を持つディクショナリを格納して送る

import socket
import os
import json
from util import Util
import ffmpeg

class VideoProcessor:
    def __init__(self, file_path, output_file_path):
        self.file_path = file_path
        self.outpute_file_path = output_file_path


    def process(self, feature_num):
        if feature_num == 1:
            self.compress_video()
        elif feature_num == 2:
            self.change_resolution()
        elif feature_num == 3:
            self.change_aspect_ratio()
        elif feature_num == 4:
            self.convert_to_audio()
        else:
            self.convert_to_gif()

    def compress_video(self, bitrate='500k'):
        (
            ffmpeg
            .input(self.file_path)
            .output(self.outpute_file_path, b=bitrate)
            .run()
        )

    def change_resolution(self, resolution='720x480'): # 解像度を変更する関数
        (
            ffmpeg
            .input(self.file_path)
            .output(self.outpute_file_path, vf=f"scale={resolution}")
            .run()
        )

    def change_aspect_ratio(self, aspect_ratio='2:1'): # アスペクト比を変更する関数
        (
            ffmpeg
            .input(self.file_path)
            .output(self.outpute_file_path, vf=f"setsar={aspect_ratio}")
            .run()
        )

    def convert_to_audio(self): # 音声ファイルへ変換する関数
        (
            ffmpeg
            .input(self.file_path)
            .output(self.outpute_file_path, acodec='mp3')
            .run()
        )

    def convert_to_gif(self, start_time, duration, fps=10): #gifへ変更する関数
        (
            ffmpeg
            .input(self.file_path, ss=start_time, t=duration)
            .output(self.outpute_file_path, vf=f"fps={fps}", pix_fmt='rgb24')
            .run()
        )


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
        self.video_path = path
        if not os.path.exists(self.video_path):
            os.makedirs(self.video_path)

    # アップロードの受け付け
    def listen_receive_file(self):
        while True:
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

                file_name = client_sock.recv(filename_length).decode()
                # jsonデータは取りあえず不要
                _ = client_sock.recv(json_length)

                # アップロードされたデータをリクエスト内のファイル名でサーバ側で用意したフォルダ内に保存
                with open(os.path.join(self.video_path, file_name), 'wb+') as f:
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
                file_name_bytes = file_name.encode('utf-8')
                header = Server.file_upload_protocol_header(len(file_name_bytes), len(jsondata_byte))
                client_sock.send(header)
                client_sock.send(file_name_bytes)
                client_sock.send(jsondata_byte)

                # 取り敢えず、１人のクライアントのリクエストを処理したら、そのまま動画編集に移る
                # なので、編集処理間は他のクライアントによるアップロードなどを受け付けない
                self.edit_video(client_sock, file_name)
                
                # 処理ずみのファイルを削除
                try:
                    self.delete_file(file_name)
                except FileNotFoundError:
                    raise FileNotFoundError(f'File not found: {file_name}')
                except PermissionError:
                    raise PermissionError(f'Permission denied: {file_name}')
                
                # クライアントソケットを閉じる
                self.close_client_socket_with_error(client_sock, None)

            # 何らかのエラーが発生した場合にerrをメッセージとしてクライアントソケットを閉じる
            except Exception as err:
                Server.close_client_socket_with_error(client_sock, err)


    def send_data_in_chunks(self, client_sock, data):
        total_sent = 0
        while total_sent < len(data):
            chunk = data[total_sent : total_sent + self.stream_rate]
            sent = client_sock.send(chunk)
            if sent == 0:
                raise RuntimeError('Socket connection broken')

            total_sent += sent


    def edit_video_handle(self, client_sock, input_file_name, feature_num):
        # input_file_nameをもとにファイルを開く
        print(f'Yay!! Video editting started!!! feature_num: {feature_num}')
        print(f'Video path: {self.video_path}, File name: {input_file_name}')
        print(type(self.video_path))
        with open(f'{self.video_path}/{input_file_name}', 'rb') as f:
            # 動画の編集処理 TODO ffmg側で何か問題が起きたときに、ここで例外を発生させてJSONデータとして格納すればクライアント側に遅れるか？
            processor = VideoProcessor(f'{self.video_path}/{input_file_name}', 'output.mp4')
            processor.process(feature_num)

            # ファイルを返す際のTCP通信で必要なデータの作成
            f.seek(0, os.SEEK_END)
            file_size = f.tell()
            f.seek(0, 0)

            err = Util.file_validation(file_size, input_file_name)
            if err != None:
                raise Exception(err)

            # media_type_lenghtは取り敢えず今回使用するmp4を0と見做して使用する
            media_type_num = 0
            media_type_num_byte = media_type_num.to_bytes(1, 'big')
            # ヘッダーの作成
            response_header = self.file_edit_protocol_header(0, len(media_type_num_byte), file_size)
            # ヘッダー・ボディの送信
            client_sock.send(response_header)
            client_sock.send(b'')
            client_sock.send(media_type_num_byte)

            while True:
                chunk = f.read(self.stream_rate)
                if not chunk:
                    break
                self.send_data_in_chunks(client_sock, chunk)


    def edit_video(self, client_sock, file_name):
        try:
            # どのような編集をしたいのかのリクエストを受け取る
            header = client_sock.recv(self.file_edit_header_size)
            json_length = int.from_bytes(header[:self.file_edit_byterange_json], 'big')
            media_type_length = int.from_bytes(header[self.file_edit_byterange_json: self.file_edit_byterange_media_type], 'big')
            _ = int.from_bytes(header[self.file_edit_byterange_media_type: self.file_edit_byterange_payload], 'big')
            print('Header received!!!')
            # jsonデータからは編集の種類をidとして取得
            json_data = json.loads(client_sock.recv(json_length).decode())
            feature_num = json_data['feature_num']
            media_type = int.from_bytes(client_sock.recv(media_type_length), 'big')

            # 取り敢えず、media_typeがmp4以外の場合はエラーを投げるようにする
            # 0 = mp4フォーマット
            if media_type != 0:
                raise Exception('Currently only mp4 is available')

            # 編集後のファイルを送信するレスポンス
            self.edit_video_handle(client_sock, file_name, feature_num)

        except Exception as err:
            Server.close_client_socket_with_error(client_sock, err)


    def delete_file(self, file_name):
        os.remove(f'{self.video_path}/{file_name}')


    @staticmethod
    def close_client_socket_with_error(client_sock, err):
        if err != None: print(f'Error: {err}')
        print('Current Client Socket Close...')
        client_sock.close()


    @staticmethod
    def file_upload_protocol_header(filename_length, json_length):
        return filename_length.to_bytes(1, 'big') + json_length.to_bytes(3, 'big')

    @staticmethod
    def file_edit_protocol_header(json_length, media_type_length, data_length):
        return json_length.to_bytes(16, 'big') + media_type_length.to_bytes(1, 'big') +  data_length.to_bytes(47, 'big')


if __name__ == '__main__':
    # ソケットの作成
    address = '0.0.0.0'
    port = 9001
    sock = Server(address, port, 'client_videos')

    # ファイルアップロードの待機
    sock.listen_receive_file()
