import keyboard
import sqlite3
from werkzeug.security import generate_password_hash
DATABASE = "database.db"

# database
conn = sqlite3.connect(DATABASE)
# sqliteを操作するカーソルオブジェクトを作成
cur = conn.cursor()

# 分散型図書館Appの司書アカウントを管理するアプリ
print("──────────────────────────"*2)
print("【分散型図書館App】の司書アカウントを管理するアプリ")
print("──────────────────────────"*2)

while True:
    # 入力してください．　新規登録：regist　削除：del　終了:exit
    input_word = input("入力してください．　新規登録:regist　削除:del　終了:exit\n")

    # 司書ユーザーの新規登録
    if(input_word == "regist"):
        input_userID = input("新規登録する司書アカウントのuserIDを入力してください．\n")
        input_password = input("passwordを入力してください．\n")

        print("本当にアカウント新規登録しますか :y")
        if keyboard.read_key():
            if(keyboard.read_key()=="y"):
                pass_hash = generate_password_hash(
                                input_password,method='pbkdf2:sha256')
                # データを挿入するSQL文
                insert_query = '''
                        INSERT INTO librarian (userID, login_hash) VALUES (?, ?);
                        '''
                # データの挿入
                cur.execute(insert_query, (input_userID, pass_hash))
                # 変更を保存
                conn.commit()

            else:
                print("キャンセルします．")

    # 司書ユーザーのアカウント削除
    if(input_word == "del"):
        input_userID = input("削除する司書アカウントのuserIDを入力してください．\n")

        print("本当にアカウントを削除しますか :y")
        if keyboard.read_key():

            
            if(keyboard.read_key()=="y"):
                # データを削除するSQL文
                delete_query = '''
                        DELETE FROM librarian WHERE userID=(?);
                        '''
                # データの挿入
                cur.execute(delete_query, (input_userID,))
                # 変更を保存
                conn.commit()
            else:
                print("ループに戻る")
    
    if(input_word == "exit"):
        print("終了します．")
        break

# detabaseの接続を切る
conn.close()