# そもそもバリデーション用の関数なのに、try, exceptキーワードを使っていないのは問題なのでは？
class Util:
    @staticmethod
    def file_validation(file_size, file_name):
        # ファイルサイズのバリデーション
        if file_size > pow(2, 32):
            return 'File must be below 2GB'
        # ファイル名からフォーマットバリデーションを行う
        if not file_name.endswith('.mp4'):
            return 'File format must be mp4'
        
        return None