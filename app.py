# 関係するコマンド
# 仮想環境の作成
# mkdir distrLibraryApp ←distrLibraryAppがフォルダ名
# cd distrLibraryApp
# py -3 -m venv venv　←これでvenvフォルダ（&中身）が作られる
# ↓PowerShellのセキュリティエラーの対策
# Set-ExecutionPolicy RemoteSigned -Scope Process　←◆毎回やる◆
# venv\Scripts\activate　←環境を有効化 ◆毎回やる◆
# pip install Flask ←Flaskをインストール
# set FLASK_APP=app ←◆毎回やる◆ appはpyファイル名
# set FLASK_ENV=development ←◆毎回やる◆
# flask run ←◆実行する毎にする◆
# ローカルでシェアするには、
# flask run --host='0.0.0.0' --port=5000

from flask import Flask, render_template,g, request,redirect,flash
import sqlite3
from datetime import datetime,date,timedelta
import calendar
import requests # GoogleBooksAPIで使う
DATABASE = "database.db"
from flask_login import UserMixin,LoginManager,login_required,login_user,logout_user
from flask_login import current_user
import os # ランダムを使う
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps # ログイン関係 adminのデコレータ関係


# 画像が入っているフォルダを指定しておく。
app = Flask(__name__, static_folder='./static')
# AIが言っていたので追加した．セッション管理？
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
#app.secret_key = os.urandom(24)
login_manager = LoginManager() # インスタンス化
login_manager.init_app(app) # Flaskアプリに紐づけ

# アップロードされたファイルを保存するディレクトリのパス
UPLOAD_FOLDER = './static/images'
# 許可するファイル形式のリスト
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif','jfif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ユーザークラス
class User(UserMixin):
    def __init__(self,userid,username,role):
        self.id = userid # current_user.idが使えるようになる
        self.username = username
        self.role = role  # 'admin' or 'user'

@login_manager.user_loader
def load_user(userid):
    # 本来ならここでDBからroleを取り出すらしい■■■■■よく分からん
    if userid[:3]=="lib":
        return User(userid,"","admin")
    return User(userid,"","user") # ここでログイン情報が決定するっぽい？

@login_manager.unauthorized_handler # 未ログインだとloginにリダイレクトする
def unauthorized():
    return redirect('/login')

# ログイン関係。デコレータ
# デコレータは@login_required，@admin_required，@user_requiredの3種類
# 謎の長文詠唱呪文
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect("/login") # 権限がない場合はログインにリダイレクト
        elif current_user.role != "admin":
            return redirect("/") # とりあえずトップページへ
        return f(*args, **kwargs)
    return decorated_function

def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect("/login")  # 権限がない場合はログインにリダイレクト
        elif current_user.role != "user":
            return redirect("/")  # 権限が異なる場合はホームにリダイレクト
        return f(*args, **kwargs)
    return decorated_function


# database なんだこれ？
def connect_db():
    rv = sqlite3.connect(DATABASE)
    rv.row_factory = sqlite3.Row # 列名を取得
    return rv
def get_db():
    if not hasattr(g,"sqlite_db"):
        g.sqlite_db = connect_db()
    return g.sqlite_db


@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('/favicon.ico')


@app.route("/")
def top():
    # ↓SQL文を実行
    book_list = get_db().execute(
                """
                SELECT collection.ISBN_uBN,
                classification.location,classification.ndc_2nd,
                book_information.title,book_information.author,book_information.revision,
                lending_status.status
                FROM collection
                INNER JOIN book_information
                ON collection.ISBN_uBN = book_information.ISBN_uBN
                INNER JOIN classification
                ON collection.classificationID = classification.classificationID
                INNER JOIN lending_status
                ON collection.collectionID = lending_status.collectionID
                """
                ).fetchall()

    return render_template('index.html',books=book_list)



@app.route('/search/', methods=['GET','POST'])
def search_title():
    # htmlのフォームから受け取った検索ワード（本のタイトル）
    req_title = request.form.get('request_book_title')

    # ↓SQL文を実行
    book_list = get_db().execute(
                """
                SELECT collection.collectionID,collection.ISBN_uBN,
                classification.location,classification.ndc_2nd,
                book_information.title,book_information.author,book_information.revision,
                lending_status.status 
                FROM collection 
                INNER JOIN book_information 
                ON collection.ISBN_uBN = book_information.ISBN_uBN 
                INNER JOIN classification 
                ON collection.classificationID = classification.classificationID 
                INNER JOIN lending_status 
                ON collection.collectionID = lending_status.collectionID 
                WHERE book_information.title LIKE ?
                """
                ,["%" + req_title + "%"]
                ).fetchall()

    return render_template('search.html',book_title=req_title,books=book_list)


@app.route("/details/<id>/", methods=['GET','POST'])
def search_details(id):
    
     # ↓SQL文を実行
    book_ISBN = get_db().execute(
                """
                SELECT book_information.ISBN_uBN,book_information.title,
                book_information.author,book_information.revision,
                book_information.explanation,book_information.book_cover
                FROM book_information
                WHERE book_information.ISBN_uBN=?;
                """,[id]
                ).fetchall()

    # 指定したISBNの蔵書の状況
    book_status_list = get_db().execute(
                    """
                    SELECT collection.collectionID,
                    classification.location,classification.ndc_2nd,
                    lending_status.status 
                    FROM collection 
                    INNER JOIN classification 
                    ON collection.classificationID = classification.classificationID 
                    INNER JOIN lending_status 
                    ON collection.collectionID = lending_status.collectionID 
                    WHERE collection.ISBN_uBN=?;
                    """,[id]
                    ).fetchall()

    # レビュー
    book_review_list = get_db().execute(
                    """
                    SELECT reviews.userID,reviews.review_title,
                    reviews.review_detail 
                    FROM reviews 
                    INNER JOIN book_information 
                    ON reviews.ISBN_uBN = book_information.ISBN_uBN 
                    WHERE reviews.ISBN_uBN=?;
                    """,[id]
                    ).fetchall()

    return render_template('detail.html',book=book_ISBN,books_status=book_status_list,
                           books_review=book_review_list)

@app.route("/login", methods=['GET','POST'])
def login():
    error_message = ""
    userid = ""

    if request.method == 'POST':
        userid = request.form.get('userid')
        password = request.form.get('password')

        if(userid[:4]=="user"): # userIDの最初の3文字がuserなら
            # ログイン（利用者ユーザー）のチェック
            user_data = get_db().execute(
                                    "SELECT user.login_hash,user.name " \
                                    "FROM user WHERE userID=?",[userid]
                                    ).fetchone()
            if user_data is not None:
                if check_password_hash(user_data[0],password):
                    user = User(userid=userid,username=user_data[1],role="user") # load_userと処理が重複している気がするが？
                    login_user(user) # ログイン処理
                    return redirect('/user/') # 利用者ページにリダイレクト
        
        elif(userid[:3]=="lib"): # userIDの最初の3文字がlibなら
            # ログイン（利用者ユーザー）のチェック
            user_data = get_db().execute(
                                    "SELECT librarian.login_hash " \
                                    "FROM librarian WHERE userID=?",[userid]
                                    ).fetchone()
            if user_data is not None:
                if check_password_hash(user_data[0],password):
                    user = User(userid=userid, username="", role="admin") # load_userと処理が重複している気がするが？
                    login_user(user) # ログイン処理
                    return redirect('/librarian/') # 利用者ページにリダイレクト
                
        error_message = "Wrong Password or Invalid Account"

    return render_template('login.html',error_message=error_message,userid=userid)


@app.route("/logout")
def logout():
    logout_user()
    return render_template('logout.html')


# 利用者ユーザー画面
@app.route("/user/", methods=['GET','POST'])
@user_required
def user():

    book_lending_list = get_db().execute(
                        """
                        SELECT lending_status.collectionID,book_information.ISBN_uBN,
                        book_information.title,book_information.author,
                        lending_status.checkout_date,lending_status.return_schedule_date 
                        FROM lending_status 
                        INNER JOIN collection 
                        ON lending_status.collectionID = collection.collectionID 
                        INNER JOIN book_information 
                        ON collection.ISBN_uBN = book_information.ISBN_uBN 
                        WHERE lending_status.userID = ?;
                        """,[current_user.id]
                        ).fetchall()
    #返却遅延回数
    overdue_time_list = get_db().execute(
                        "SELECT user.delay_time " \
                        "FROM user " \
                        "WHERE user.userID = ?;",[current_user.id]
                        ).fetchone()
    overdue_time = overdue_time_list[0]

    #直近予約中の蔵書
    book_nearest_reservation_list = get_db().execute(
                        """
                        SELECT lending_status.collectionID,book_information.ISBN_uBN,
                        book_information.title,book_information.author 
                        FROM lending_status 
                        INNER JOIN collection 
                        ON lending_status.collectionID = collection.collectionID 
                        INNER JOIN book_information 
                        ON collection.ISBN_uBN = book_information.ISBN_uBN 
                        WHERE lending_status.nearest_reservation_userID =?;
                        """,[current_user.id]
                        ).fetchall()

    #事前予約中の蔵書
    book_schedule_list = get_db().execute(
                        """
                        SELECT schedule_results.collectionID,book_information.ISBN_uBN,
                        book_information.title,book_information.author, 
                        schedule_results.checkout_date,schedule_results.return_date 
                        FROM schedule_results 
                        INNER JOIN collection 
                        ON schedule_results.collectionID = collection.collectionID 
                        INNER JOIN book_information 
                        ON collection.ISBN_uBN = book_information.ISBN_uBN 
                        WHERE schedule_results.userID =? 
                        AND schedule_results.schedule_results_flag = 1;
                        """,[current_user.id]
                        ).fetchall()

    return render_template('user.html',books_lending=book_lending_list,overdue_time=overdue_time,
                           book_nearest_reservations=book_nearest_reservation_list,
                           books_schedule=book_schedule_list)


# 本を借りる（利用者ユーザー）
@app.route("/borrow/", methods=['GET','POST'])
@user_required
def borrow():

    # 貸出中の蔵書をリスト化
    book_lending_list = get_db().execute(
                        """
                        SELECT lending_status.collectionID,book_information.ISBN_uBN,
                        book_information.title,book_information.author,
                        lending_status.checkout_date,lending_status.return_schedule_date 
                        FROM lending_status 
                        INNER JOIN collection 
                        ON lending_status.collectionID = collection.collectionID 
                        INNER JOIN book_information 
                        ON collection.ISBN_uBN = book_information.ISBN_uBN 
                        WHERE lending_status.userID =?;
                        """,[current_user.id]
                        ).fetchall()

    # htmlのフォームから受け取った検索ワード（本の蔵書ID）(受け取った変数は文字列)
    req_collectionID = request.form.get('request_lend_collectionID')
    try:
        req_collectionID = int(req_collectionID) #文字列を数値に変換してみる
    except ValueError:
        over_flag = 9 # htmlのフォームから受け取った本の蔵書IDが数字でない不適切な場合

    if(req_collectionID==""): # エラー回避のため
        over_flag = 2

    elif(isinstance(req_collectionID,int) and req_collectionID>0):
        # 借りたい本が貸出中になっていないかチェック
        # fetchallの戻り値はリスト型のタプル．data = [(1, "Alice", 25), (2, "Bob", 30)]　←こんな感じ
        is_on_loan_list = get_db().execute(
                            "SELECT lending_status.status " \
                            "FROM lending_status " \
                            "WHERE lending_status.collectionID =?;",[req_collectionID]
                            ).fetchall()
    
        # 借りたい本が直近予約になっていないかチェック
        # nearest_reservation_userID に値が入っていれば直近予約がある状態．
        nearest_reserved = get_db().execute(
                                "SELECT lending_status.nearest_reservation_userID " \
                                "FROM lending_status " \
                                "WHERE lending_status.collectionID=?;",[req_collectionID]
                                ).fetchall()

        #　その本を自分で事前予約していないかチェック．
        self_reserved_list = get_db().execute(
                                    """
                                    SELECT schedule_results.checkout_date, schedule_results.return_date
                                    FROM schedule_results
                                    WHERE schedule_results.collectionID=?
                                    AND schedule_results.schedule_results_flag=?
                                    AND schedule_results.userID=?; 
                                    """,[req_collectionID,1,current_user.id]
                                    ).fetchall()
        # 自分でやった事前予約の期間中かチェック
        # 今日の日付が貸出予約～返却予定日に入っているか確認
        now_date = date.today()
        s_format = '%Y/%m/%d'
        
        for  self_reserved in self_reserved_list:
            from_date = datetime.strptime(self_reserved[0], s_format).date()
            until_date = datetime.strptime(self_reserved[1], s_format).date()

            if from_date <= now_date <= until_date:
                #　自分でやった事前予約を（全て）過去のものにする。
                get_db().execute(
                            """
                            UPDATE schedule_results SET
                            schedule_results_flag=?
                            WHERE schedule_results.collectionID=?
                            AND schedule_results.userID=?;
                            """,[0,req_collectionID,current_user.id]
                            )
                get_db().commit()
                break

        # その本の事前予約をリストアップする。
        reservation_list = get_db().execute(
                                    """
                                    SELECT schedule_results.checkout_date, schedule_results.return_date
                                    FROM schedule_results
                                    WHERE schedule_results.collectionID=?
                                    AND schedule_results.schedule_results_flag=?; 
                                    """,[req_collectionID,1]
                                    ).fetchall()
    
        # 今日の日付が事前予約の期間に入っていないか確認する。
        now_date = date.today()
        end_date = now_date # 貸出最終日。初期化
        is_reserved = False
        for reservation in reservation_list:
            # 文字列の例"2025/4/1"
            s_format = '%Y/%m/%d'
            from_date = datetime.strptime(reservation[0], s_format).date()
            until_date = datetime.strptime(reservation[1], s_format).date()
            if(from_date <= now_date <= until_date):
                is_reserved=True
                break
        if(nearest_reserved[0][0]==None and not (is_reserved)): #直近予約・事前予約がない場合
            # 3週間（21日間）に他の予約が入っていないかチェック。
            # 何日間（最大21日間）だけ借りれるか調べる
            for i in range(21):
                diff_day = timedelta(days=i+1)
                exam_day = now_date + diff_day
                is_fail = False
                for reservation in reservation_list:
                    s_format = '%Y/%m/%d'
                    from_date = datetime.strptime(reservation[0], s_format).date()
                    if(from_date <= exam_day):
                        is_fail=True
                        break
                if(is_fail==True):
                    # 貸し出し可能な最後の日（exam_dayから1日引き算する）
                    end_date = exam_day - timedelta(days=1)
                    break
            if(is_fail==False): # 21日間、すべて予約可な場合
                end_date = exam_day

        if now_date == end_date: #now_dateとend_dateが同じなら借りられない
            over_flag = 8 # 明日の予約が埋まっている為に貸出不可

        # 貸し出し冊数が上限を超えていないかチェック。
        elif(len(book_lending_list)>=5): # 要素数が5超の場合は貸出不可
            over_flag = 1
        #elif(book_lending_list==[] or is_on_loan_list==[]): # 貸出リクエストが空の場合
        elif(req_collectionID==None): # 貸出リクエストが空の場合 これあってるのか？
            over_flag = 2
        elif(is_on_loan_list[0][0]=="貸出中" or is_on_loan_list[0][0]=="貸出不可"): # 貸出ができない場合
            over_flag = 3
        elif(nearest_reserved!=[] and nearest_reserved[0][0]!=None): # 直近予約が入っている場合
            over_flag = 4
        else: # 問題ない場合
            over_flag = 0

            # 蔵書の本を借りるSQL文
            # now_dateからend_dayまで借りれる。
            get_db().execute(
                        """
                        UPDATE lending_status SET
                        status='貸出中',userID=?,
                        checkout_date=?,
                        return_schedule_date=?
                        WHERE lending_status.collectionID=?;
                        """,[current_user.id,now_date.strftime('%Y/%m/%d'),end_date.strftime('%Y/%m/%d'),
                             req_collectionID]
                        )
            get_db().commit()
    
    else:
        over_flag = 9 # htmlのフォームから受け取った本の蔵書IDが数字でない不適切な場合

    # 表示用に貸出中の蔵書を再度リスト化
    book_lending_list = get_db().execute(
                        """
                        SELECT lending_status.collectionID,book_information.ISBN_uBN,
                        book_information.title,book_information.author,
                        lending_status.checkout_date,lending_status.return_schedule_date 
                        FROM lending_status 
                        INNER JOIN collection 
                        ON lending_status.collectionID = collection.collectionID 
                        INNER JOIN book_information 
                        ON collection.ISBN_uBN = book_information.ISBN_uBN 
                        WHERE lending_status.userID =?;
                        """,[current_user.id]
                        ).fetchall()

    return render_template('borrow.html',books_lending=book_lending_list,
                           over_flag=over_flag)


# 本の返却
@app.route("/return_book/<collectionID>/")
@user_required
def return_book(collectionID):

    # 返却前の情報を一時記憶する
    before_status = get_db().execute(
                                "SELECT lending_status.checkout_date, lending_status.return_schedule_date " \
                                "FROM lending_status " \
                                "WHERE lending_status.collectionID=? " \
                                "AND lending_status.status='貸出中';" 
                                ,[collectionID]
                                ).fetchone()
    schedule_return_date = datetime.strptime(before_status[1], '%Y/%m/%d') # 返却予定日を日時型に変換

    # 返却前の貸出遅延回数を一時記憶する
    before_delay_time_get = get_db().execute(
                                "SELECT user.delay_time " \
                                "FROM user " \
                                "WHERE user.userID=?"
                                ,[current_user.id]
                                ).fetchone()
    delay_time = before_delay_time_get[0]

    # 蔵書の本を返却するSQL文
    get_db().execute(
                "UPDATE lending_status SET " \
                "status='貸出可',userID=''," \
                "checkout_date='',return_schedule_date='' " \
                "WHERE lending_status.collectionID=?;"
                ,[collectionID]
                )
    get_db().commit()
    
    # 返却予定日を過ぎている場合は返却超過カウント+1
    if ( (datetime.today()-schedule_return_date).days > 0 ) :
        delay_time = delay_time +1
        get_db().execute(
                "UPDATE user SET " \
                "delay_time=? " \
                "WHERE userID=?;"
                ,[delay_time,current_user.id]
                )
    get_db().commit()

    return render_template('return_book.html',delay_time=delay_time)


# レビュー（クチコミ）の書き込み
@app.route("/review_write/<ISBN_uBN>/", methods=['GET','POST'])
@user_required
def review_write(ISBN_uBN):
    
    is_done = False # 書き込み完了フラグ
    is_2ndtime = False # 初期化

    # 書籍のタイトルと著者を取得する。fetchoneの方が楽そう？
    book = get_db().execute(
                        "SELECT book_information.title,book_information.author " \
                        "FROM book_information " \
                        "WHERE book_information.ISBN_uBN=?;"
                        ,[ISBN_uBN]
                        ).fetchone()
    
    # htmlのフォームから受け取ったレビューのタイトルと内容
    req_review_title = request.form.get('review_title')
    req_review_detail = request.form.get('review_detail')


    # 一回目に/review_writeにアクセスしたときにはここを回避する
    if(req_review_title==None):
        pass
    else:
        is_2ndtime = True
        if req_review_title and req_review_detail:
            # レビューを書込するSQL文
            get_db().execute(
                        "INSERT INTO reviews " \
                        "(ISBN_uBN,userID,review_title,review_detail) " \
                        "VALUES " \
                        "(?,?,?,?);"
                        ,[ISBN_uBN,current_user.id,req_review_title,req_review_detail]
                        ).fetchall()
            get_db().commit()
            is_done = True # 書き込み完了フラグ

    return render_template('review_write.html',
                           ISBN_uBN=ISBN_uBN,book=book,is_done=is_done,
                           is_2ndtime=is_2ndtime)


# 事前予約・直近予約
# カレンダーを表示して日付を入力するページ。
@app.route("/reservation/", methods=['GET','POST'])
@user_required
def reservation():

    # 現在の年と月を取得
    now = date.today()
    year = now.year
    month = now.month

    # カレンダーを作成
    cal = calendar.Calendar(firstweekday=6) # 日曜はじまり
    month_days = cal.monthdayscalendar(year, month)
    next1_month_days = cal.monthdayscalendar(year, month+1)
    next2_month_days = cal.monthdayscalendar(year, month+2)
    next3_month_days = cal.monthdayscalendar(year, month+3)
    
    # htmlのフォームから受け取った蔵書ID
    req_collectionID = request.form.get('request_reservation_collectionID')

    # カレンダーに対応する2次元リスト
    cal_lent = [["○" for _ in range(31+1)] for _ in range(4)]

    # その本の事前予約をリストアップする。
    reservation_list = get_db().execute(
                                    "SELECT schedule_results.checkout_date, schedule_results.return_date " \
                                    "FROM schedule_results " \
                                    "WHERE schedule_results.collectionID=? " \
                                    "AND schedule_results.schedule_results_flag=?;"   
                                    ,[req_collectionID,1]
                                    ).fetchall()
    if reservation_list != None:
        for reservation in reservation_list:
            # yyyy/mm/dd
            start_yymmdd = reservation[0]
            end_yymmdd = reservation[1]
            start_yy = int(start_yymmdd[:3+1])
            start_mm = int(start_yymmdd[5:6+1])
            start_dd = int(start_yymmdd[8:9+1])
            end_yy = int(end_yymmdd[:3+1])
            end_mm = int(end_yymmdd[5:6+1])
            end_dd = int(end_yymmdd[8:9+1])

            # もし，startとendで月が異なればそのstar日～月末，翌月～end日までを貸で埋める
            # 年をまたいでもこれでいけるはず
            if(start_yy==end_yy and start_mm!=end_mm):
                for i in range(start_dd,32):
                    cal_lent[start_mm-month][i] = "×"
                for i in range(1,end_dd+1):
                    cal_lent[start_mm-month+1][i] = "×"
            # もし，startとendで月が同じならばstart～endまでを貸で埋める
            if(start_yy==end_yy and start_mm==end_mm):
                for i in range(start_dd,end_dd+1):
                    cal_lent[start_mm-month][i] = "×"

    return render_template('reservation.html',year=year, month=month, month_days=month_days,
                           next1_month_days=next1_month_days,next2_month_days=next2_month_days,
                           next3_month_days=next3_month_days,
                           cal_lent=cal_lent,
                           req_collectionID=req_collectionID)


# 事前予約の登録確認
@app.route("/reservation_confirm/<collectionID>/", methods=['GET','POST'])
@user_required
def reservation_confirm(collectionID):
    
    is_null = False # 初期化 collectionIDに問題ありの場合
    is_error = False # 初期化 事前予約開始日に問題ありの場合
    is_over = False # 初期化　事前予約数が5を超えている
    start_date = datetime(2000, 4, 1) # エラー回避
    end_date = datetime(2000, 4, 1) # エラー回避
    # collectionIDが空だった場合
    if(collectionID==None):
        is_null = True # 蔵書IDに不備。
    else: # 問題ない場合

        # 自分が事前予約を何個しているか確認する。（最大で5個まで）
        my_reservation_list = get_db().execute(
                                    """
                                    SELECT schedule_results.collectionID 
                                    FROM schedule_results 
                                    WHERE schedule_results.userID=?
                                    AND schedule_results.schedule_results_flag=?;
                                    """,[current_user.id,1]
                                    ).fetchall()
        my_list = len(my_reservation_list)
        
        if my_list > 5 :
            is_over = True # 事前予約数が5を超えている（不適）
        else:

            # その本の事前予約をリストアップする。（貸出実績日、返却予定日）
            reservation_list = get_db().execute(
                                        "SELECT schedule_results.checkout_date, schedule_results.return_date " \
                                        "FROM schedule_results " \
                                        "WHERE schedule_results.collectionID=?" \
                                        "AND schedule_results.schedule_results_flag=?;"   
                                        ,[collectionID,1]
                                        ).fetchall()

            # htmlのフォームから受け取った予約開始日
            lending_schedule_date_str = request.form.get('req_lending_schedule_date')
            # 文字列を日付型に変換できるか（フォーマットが正しいか）チェックする。
            try:
                start_date = datetime.strptime(lending_schedule_date_str, "%Y-%m-%d")
            except ValueError:
                is_error = True
                start_date = datetime.strptime("2000/1/1",'%Y/%m/%d') #仮
                end_date = datetime.strptime("2000/1/1",'%Y/%m/%d') #仮
                print("***errror date value")
            else:
                # 入力された日が過去日になっていないかチェック
                if start_date < datetime.now() :
                    is_error = True
                # 入力された日が3ヶ月(30*3=90日)以上未来になっていないかチェック
                if 90 <= (start_date - datetime.now()).days :
                    is_error = True

                # 今日の日付が事前予約の期間に入っていないか確認する。
                # 文字列の例"2025/4/1"
                end_date = start_date # 貸出最終日。初期化
                is_reserved = False # 既に予約がはいっているフラグ
                s_format = '%Y/%m/%d'
                for reservation in reservation_list:
                    from_date = datetime.strptime(reservation[0], s_format) #予約が入っている開始日
                    until_date = datetime.strptime(reservation[1], s_format) #予約が入っている最終日
                    if(from_date <= start_date <= until_date):
                        is_reserved=True # 既に予約が入っている
                        break
                
                if(is_reserved or is_error): #問題ありの場合
                    is_error = True

                else: #直近予約・事前予約がない場合
                    # 3週間（21日間）に他の予約が入っていないかチェック。
                    # 何日間（最大21日間）だけ借りれるか調べる
                    is_fail = False
                    for i in range(21):
                        diff_day = timedelta(days=i+1)
                        exam_day = start_date + diff_day
                        
                        for reservation in reservation_list:
                            s_format = '%Y/%m/%d'
                            from_date = datetime.strptime(reservation[0], s_format)
                            until_date = datetime.strptime(reservation[1], s_format)
                            if(from_date <= exam_day <= until_date ):
                                is_fail=True
                                break
                        if(is_fail==True):
                            # 貸し出し可能な最後の日（exam_dayから1日引き算する）
                            end_date = exam_day - timedelta(days=1)
                            break
                    if(is_fail==False): # 21日間、すべて予約可な場合
                        end_date = exam_day
                    if start_date.date() == end_date.date(): #start_dateとend_dayが同じなら借りられない
                        is_error = True # 借りられない
                    
                    elif( not is_error ):
                        # start_dateからend_dayまで借りれる。
                        get_db().execute(
                                    "INSERT INTO schedule_results " \
                                    "(userID,collectionID,checkout_date,return_date," \
                                    "schedule_results_flag) " \
                                    "VALUES " \
                                    "(?,?,?,?,?);"
                                    ,[current_user.id,collectionID,
                                    start_date.strftime('%Y/%m/%d'),end_date.strftime('%Y/%m/%d'),1]
                                    )
                        get_db().commit()
        
                    

    return render_template('reservation_confirm.html',collectionID=collectionID,
                           lending_schedule_date=start_date.strftime('%Y/%m/%d'),
                           return_schedule_date=end_date.strftime('%Y/%m/%d'),
                           is_null=is_null,is_error=is_error,is_over=is_over)

# 事前予約を（user画面から）キャンセルする
@app.route("/cancel/", methods=['GET','POST'])
@user_required
def cancel():

    # htmlのフォームから受け取った蔵書ID
    req_cancel_collectionID = request.form.get('request_cancel_collectionID')
    
    # このユーザーのこの蔵書IDの事前予約をすべて←！破棄する。
    #schedule_results_flag=2 で無効
    get_db().execute(
                    """
                    UPDATE schedule_results 
                    SET schedule_results_flag = ?
                    WHERE userID=?
                    AND schedule_results_flag = ?
                    AND collectionID = ?
                    """,[2,current_user.id,1,req_cancel_collectionID]
                    )
    get_db().commit()
    is_done = True

    return render_template('cancel.html',is_done=is_done,
                           collectionID=req_cancel_collectionID)


@app.route("/history/")
@user_required
def history():
    
    # 貸出履歴を表示する
    history_list = get_db().execute(
                                """
                                SELECT schedule_results.collectionID, book_information.ISBN_uBN,
                                book_information.title, book_information.author,
                                book_information.revision,
                                schedule_results.checkout_date,schedule_results.return_date 
                                FROM schedule_results 
                                INNER JOIN collection 
                                ON schedule_results.collectionID = collection.collectionID 
                                INNER JOIN book_information 
                                ON collection.ISBN_uBN = book_information.ISBN_uBN 
                                WHERE schedule_results.userID=?
                                AND schedule_results.schedule_results_flag=1;
                                """,[current_user.id]
                                ).fetchall()
    
    return render_template('history.html',histories=history_list)


#利用者ユーザーのパスワードを自分で変更する
@app.route("/change_password/",methods=['GET','POST'])
@user_required
def change_password():

    is_done = False # 初期化
    
    if request.method == 'POST':
        # htmlのフォームから受け取った新規利用者アカウントのpassward
        password = request.form.get('request_new_password')
        # パスワードのハッシュ値
        pass_hash = generate_password_hash(password,method='pbkdf2:sha256')
        # SQL
        get_db().execute(
                        """
                        UPDATE user 
                        SET login_hash = ?
                        WHERE userID=?;
                        """,[pass_hash,current_user.id]
                        )
        get_db().commit()

        is_done = True

    return render_template('change_password.html',is_done=is_done)

#------------------------------
# 司書ユーザー画面
@app.route("/librarian/", methods=['GET','POST'])
@admin_required
def librarian():
    pass
    return render_template('librarian.html')


# 利用者アカウントの新規登録
# 入力→再読み込みで処理する
@app.route("/lib_account_register/", methods=['GET','POST'])
@admin_required
def lib_account_register():

    userid = 0 # 初期化
    is_newed = False #初期化
    password = 0 # 初期化
    is_error = 0 # 初期化 いろいろな不正フラグ

    if request.method == 'POST':
        # htmlのフォームから受け取った新規利用者アカウントのuerID
        userid = request.form.get('request_new_userID')
        # htmlのフォームから受け取った氏名
        req_new_name = request.form.get('request_new_name')
        # htmlのフォームから受け取った新規利用者アカウントのpassward
        password = request.form.get('request_new_password')

        is_newed = False # 初期化 登録されましたフラグ

        if( userid and password ): # ""(空文字)やNoneではない場合

            user_check = get_db().execute(
                                    "SELECT userID FROM user WHERE userID=?",
                                    [userid]
                                    ).fetchone()

            if (not user_check): # ユーザー名が重複していなければOK
                # パスワードのハッシュ値
                pass_hash = generate_password_hash(password,method='pbkdf2:sha256')
                get_db().execute(
                            "INSERT INTO user " \
                            "(userID,login_hash,name,delay_time) " \
                            "VALUES (?,?,?,?)",
                            [userid,pass_hash,req_new_name,0]
                            )
                get_db().commit()
                is_error = 1 # 成功
                is_newed = True
            else: # 既にそのユーザーIDが登録されている場合
                is_error = 2
        
        else:
            is_error = 3 # userIDまたはpasswordが無い

    return render_template('lib_account_register.html',is_newed=is_newed,
                           is_error=is_error)


# 利用者アカウントの削除
# 入力→再読み込みで処理する
@app.route("/lib_account_delete/", methods=['GET','POST'])
@admin_required
def lib_management():

    req_delete_userID = None # 初期化

    if request.method == 'POST':
        # htmlのフォームから受け取った削除アカウントのuerID
        req_delete_userID = request.form.get('request_delete_userID')

    is_deleted = False # 初期化

    if(req_delete_userID!=None):
        get_db().execute(
                    "DELETE FROM user "
                    "WHERE userID='"+req_delete_userID+"';"
                    )
        get_db().commit()
        is_deleted = True

    return render_template('lib_account_delete.html',is_deleted=is_deleted)


@app.route("/lib_history/", methods=['GET','POST'])
@admin_required
def lib_history():

    req_collectionID = request.form.get('request_collectionID')

    # 貸出履歴を表示する
    history_list = get_db().execute(
                                """
                                SELECT schedule_results.collectionID, book_information.ISBN_uBN,
                                book_information.title, book_information.author,
                                book_information.revision,
                                schedule_results.checkout_date,schedule_results.return_date 
                                FROM schedule_results 
                                INNER JOIN collection 
                                ON schedule_results.collectionID = collection.collectionID 
                                INNER JOIN book_information 
                                ON collection.ISBN_uBN = book_information.ISBN_uBN 
                                WHERE schedule_results.collectionID=?
                                AND schedule_results.schedule_results_flag=0;
                                """,[req_collectionID]
                                ).fetchall()
    
    return render_template('lib_history.html',
                           histories=history_list,collectionID=req_collectionID)


# レビュー（クチコミ）の書き込みの管理（削除）
@app.route("/lib_review/", methods=['GET','POST'])
@admin_required
def lib_review():
    
    # htmlのフォームから受け取ったレビューのタイトルと内容
    req_ISBN_uBN = request.form.get('request_ISBN_uBN') # 表示用 前のページから受け取る
    req_reviewID = request.form.get('del_reviewID') # 操作用

    book = [] # エラー回避のため初期化
    book_review_list =[[0]] # エラー回避のため初期化

    if(req_ISBN_uBN != None):
        # 書籍のタイトルと著者を取得する。fetchoneの方が楽そう？
        book = get_db().execute(
                        "SELECT book_information.title,book_information.author " \
                        "FROM book_information " \
                        "WHERE book_information.ISBN_uBN=?;"
                        ,[req_ISBN_uBN]
                        ).fetchone()
        
        # レビュー一覧を取得する
        book_review_list = get_db().execute(
                        """
                        SELECT reviews.id,reviews.userID,reviews.review_title,
                        reviews.review_detail 
                        FROM reviews 
                        INNER JOIN book_information 
                        ON reviews.ISBN_uBN = book_information.ISBN_uBN 
                        WHERE reviews.ISBN_uBN=?;
                        """,[req_ISBN_uBN]
                        ).fetchall()

    is_done = False # 初期化。レビュー削除完了フラグ

    # 一回目に/review_writeにアクセスしたときにはここを回避する
    if(req_reviewID==None):
        pass
    else:
        # レビューを削除するSQL文
        get_db().execute(
                    "DELETE FROM reviews " \
                    "WHERE id=?;"
                    ,[req_reviewID]
                    ).fetchall()
        get_db().commit()
        is_done = True # レビュー削除完了フラグ

    return render_template('lib_review.html',book=book,
                           ISBN_uBN=req_ISBN_uBN,
                           books_review=book_review_list,
                           is_done=is_done)


# 本の新規登録の入力画面表示
@app.route("/lib_new_book/")
@admin_required
def lib_new_book():

    pass

    return render_template('lib_new_book.html')


# アップロードするファイル形式のバリデーション関数
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# 本の新規登録の処理・完了表示画面
@app.route("/lib_new_result/", methods=['GET','POST'])
@admin_required
def lib_new_result():

    # htmlのフォームから受け取った新規書籍の情報
    req_ISBN_uBN = request.form.get('request_ISBN_uBN')
    req_title = request.form.get('request_title')
    req_author = request.form.get('request_author')
    req_revision = request.form.get('request_revision')
    req_explanation = request.form.get('request_explanation')
    req_book_cover = request.form.get('request_book_cover')
    req_classificationID = request.form.get('request_classificationID')

    # リクエストがポストかどうかの判別
    if request.method == 'POST':
        # ファイルがなかった場合の処理
        if 'request_book_cover' not in request.files:
            flash('ファイルがありません')
            return redirect("/lib_new_book/")
        # データの取り出し
        file = request.files['request_book_cover']
        # ファイル名がなかった時の処理
        if file.filename == '':
            flash('ファイルがありません')
            return redirect("/lib_new_book/")
        # ファイルのチェック
        if file and allowed_file(file.filename):
            # 危険な文字を削除（サニタイズ処理）←日本語文字が消える！
            #filename = secure_filename(file.filename)
            filename = file.filename
            # ファイルの保存
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            # アップロード後のページに転送
            #return redirect(url_for('uploaded_file', filename=filename))
        req_book_cover = filename

    image_url = "" # エラー回避
    
    is_done = 0 # 初期化
    # 書棚・分類IDが空になっていないか確認
    if (req_classificationID==None):
        is_done = 2
    # 10桁、13桁ならGoogleBooksAPIで書籍情報を得る
    elif(len(req_ISBN_uBN)==10 or len(req_ISBN_uBN)==13):
        try:
            result  = requests.get("https://www.googleapis.com/books/v1/volumes?q=isbn:"+req_ISBN_uBN)
        except:
            print("GoogleBooksAPI通信エラー")
        else:
            #返却されたJSONを辞書型に変換する。
            data = result.json()
            req_title = data["items"][0]["volumeInfo"]["title"]
            req_author = data["items"][0]["volumeInfo"]["authors"][0] # 著名者が複数の場合は無視する
            if "description" in data["items"][0]["volumeInfo"]:
                req_explanation = data["items"][0]["volumeInfo"]["description"]
            else:
                req_explanation = "情報はありません"
            if ("imageLinks" in data["items"][0]["volumeInfo"] and 
                "thumbnail" in data["items"][0]["volumeInfo"]["imageLinks"]):
                image_url = data["items"][0]["volumeInfo"]["imageLinks"]["thumbnail"]
                req_book_cover = req_ISBN_uBN+".jfif"
            else:
                req_book_cover = "NA.jpg"

            get_db().execute(
                    """
                    INSERT INTO book_information 
                    (ISBN_uBN,title,author,revision,explanation,book_cover) 
                    VALUES 
                    (?,?,?,'',?,?);
                    """,[req_ISBN_uBN,req_title,req_author,req_explanation,req_book_cover]
                    )
            get_db().execute(
                    "INSERT INTO collection " \
                    "(ISBN_uBN,classificationID) " \
                    "VALUES " \
                    "('"+req_ISBN_uBN+"','"+req_classificationID+"');"
                    )
            get_db().execute(
                    """
                    INSERT INTO lending_status 
                    (status) 
                    VALUES 
                    ('貸出可');
                    """
                    )
            get_db().commit()

            # 書影の画像ファイルをURLから保存する
            if image_url != "":
                image_file_name = "static/images/"+req_ISBN_uBN+".jfif"
                response = requests.get(image_url)
                image = response.content
                with open(image_file_name, "wb") as f:
                    f.write(image)

            is_done = 1

    # 8桁なら雑誌ID。全項目を手動入力。
    # 書影の画像ファイルは既にフォルダに入っているとする。←これでいいのか？
    elif(len(req_ISBN_uBN)==8):
        get_db().execute(
                    """
                    INSERT INTO book_information 
                    (ISBN_uBN,title,author,revision,explanation,book_cover) 
                    VALUES 
                    (?,?,?,?,?,?);
                    """,[req_ISBN_uBN,req_title,req_author,req_revision,req_explanation,req_book_cover]
                    )
        get_db().execute(
                    "INSERT INTO collection " \
                    "(ISBN_uBN,classificationID) " \
                    "VALUES " \
                    "(?,?);"
                    ,[req_ISBN_uBN,req_classificationID]
                    )
        get_db().execute(
                    "INSERT INTO lending_status " \
                    "(status) " \
                    "VALUES " \
                    "('貸出可');"
                    )
        get_db().commit()

        is_done = 1

    # それ以外はISBN・雑誌IDの入力ミス
    else:
        is_done = 3

    return render_template('lib_new_result.html',is_done=is_done)


# 老朽した本の破棄の入力画面表示
@app.route("/lib_dispose_book/")
@admin_required
def lib_dispose_book():

    pass

    return render_template('lib_dispose_book.html')


# 本の新規登録の処理・完了表示画面
@app.route("/lib_dispose_result/", methods=['GET','POST'])
@admin_required
def lib_dispose_result():

    is_done = False # 初期化

    # htmlのフォームから受け取った新規書籍の情報
    req_collectionID = request.form.get('request_collectionID')

    get_db().execute(
                    """
                    UPDATE lending_status 
                    SET status = ?
                    WHERE collectionID = ?
                    """,["破棄",req_collectionID]
                    )
    get_db().commit()

    is_done = True

    return render_template('lib_dispose_result.html',
                           collectionID=req_collectionID,is_done=is_done)


#利用者ユーザーのパスワードを再設定する
@app.route("/lib_change_password/",methods=['GET','POST'])
@admin_required
def lib_change_password():

    is_done = False # 初期化
    is_exits = False # 初期化
    
    if request.method == 'POST':
        # htmlのフォームから受け取った利用者アカウントのID
        userID = request.form.get('request_userID')
        # htmlのフォームから受け取った規利用者アカウントの再設定passward
        password = request.form.get('request_new_password')
        # パスワードのハッシュ値
        pass_hash = generate_password_hash(password,method='pbkdf2:sha256')
        
        #そのuserIDが実在するか確認する
        userID_exits = get_db().execute(
                        """
                        SELECT user.userID 
                        FROM user 
                        WHERE user.userID=?;
                        """,[userID]
                        ).fetchone()
        #そのuserIDが実在する場合
        if userID_exits:
            is_exits = True
            # SQL
            get_db().execute(
                            """
                            UPDATE user 
                            SET login_hash = ?
                            WHERE userID=?;
                            """,[pass_hash,userID]
                            )
            get_db().commit()

        is_done = True #POSTを受け取ったフラグ

    return render_template('lib_change_password.html',
                           is_done=is_done,is_exits=is_exits)

# ■■■■■■■■■■■■■■■■■■■■■■■■■■■■■■

if __name__ == "__main__":
    app.run(debug = True) # 実稼働環境では、debug = Trueを消すこと


