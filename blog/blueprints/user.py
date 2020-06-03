from .auth import token_auth
from flask import request, Blueprint, jsonify, g
from datetime import datetime
from ..extensions import db
from .post import error_response
from ..model import user, comment, article  # model引用必须在db和login_manager之后，以免引起循环引用

user_bp = Blueprint('user', __name__)


# 返回id对应的用户信息
@user_bp.route('/<id>', methods=['GET'])
@token_auth.login_required
def get_user(id):
     que = user.query.get_or_404(id)
     if g.current_user == que:
          return jsonify(que.to_dict())    # 如果查询自己的信息
     data = que.to_dict()
     data['is_following'] = g.current_user.is_following(que)     # 如果是查询其它用户，添加 是否已关注过该用户 的标志位
     return jsonify(data)


# 修改id对应的用户信息
@user_bp.route('/<id>', methods=['PUT'])
def update(id):
     data = request.get_json()
     que = user.query.get_or_404(id)
     que.about_me = data['about_me']
     que.sex = data['sex']
     db.session.add(que)
     db.session.commit()
     return 'Success'


# 关注用户
@user_bp.route('/follow/<id>', methods=['GET'])
@token_auth.login_required
def follow(id):
     que = user.query.get_or_404(id)
     if g.current_user == que:
          return 'Wrong'
     if g.current_user.is_following(que):
          return 'Wrong'
     g.current_user.follow(que)
     que.add_new_notification('new_received_followers', que.new_received_followers())  # 更新未读通知数目
     db.session.commit()
     return 'Success'


# 取消关注
@user_bp.route('/unfollow/<id>', methods=['GET'])
@token_auth.login_required
def unfollow(id):
     que = user.query.get_or_404(id)
     if g.current_user == que:
          return 'Wrong'
     if not g.current_user.is_following(que):
          return 'Wrong'
     g.current_user.unfollow(que)
     db.session.commit()
     return 'Success'


# 获得用户id的所有粉丝
@user_bp.route('/getOnesFans/<id>', methods=['GET'])
@token_auth.login_required
def get_ones_fans(id):
    que = user.query.get_or_404(id)                 # 得到id对应的用户que
    page = request.args.get('page', 1, type=int)
    per_page = 4
    pagi = user.pagnitede_dict(que.followers, page, per_page, 'user.get_ones_fans', id=id)  # que.followers得到que的所有粉丝，分页
    for item in pagi['items']:
        item['is_following'] = g.current_user.is_following(user.query.get(item['id']))    # 对于que的每个粉丝item['id']，查看g.current_user是否关注过
        res = db.engine.execute("select * from followers where follower_id={} and followed_id={}".format(item['id'], que.id))   # 获得关联表中timestamp
        item['timestamp'] = list(res)[0][2]
    mark = request.args.get('mark')
    if mark == 'true':  # 字符串形式
        pagi['has_new'] = False
        que.last_received_followers_read_time = datetime.utcnow()
        for item in pagi['items']:
            item['is_new'] = False
    else:
        last_read_time = g.current_user.last_received_followers_read_time or datetime(1900, 1, 1)
        for item in pagi['items']:
            if item['timestamp'] > last_read_time:
                item['is_new'] = True
                pagi['has_new'] = True
    db.session.commit()
    return jsonify(pagi)


# 获得用户id的所有关注者（大神）
@user_bp.route('/getOnesFolloweds/<id>', methods=['GET'])
@token_auth.login_required
def get_ones_followeds(id):
    que = user.query.get_or_404(id)                 # 得到id对应的用户que
    page = request.args.get('page', 1, type=int)
    per_page = 4
    pagi = user.pagnitede_dict(que.followeds, page, per_page, 'user.get_ones_followeds', id=id)  # que.followers得到que的所有粉丝，分页
    for item in pagi['items']:
         item['is_following'] = g.current_user.is_following(user.query.get(item['id']))                     # 对于que的每个粉丝item['id']，查看g.current_user是否关注过
    return jsonify(pagi)


# 获得用户id得到的所有评论
@user_bp.route('/reveivedCommets/<id>', methods = ['GET'])
@token_auth.login_required
def get_received_comments(id):
    que = user.query.get_or_404(id)
    if que != g.current_user:
        return error_response(403)
    page = request.args.get('page', 1, type=int)
    per_page = 5
    post_ids = [post.id for post in que.posts.all()]          # 用户发表的所有文章的id
    pagi = user.pagnitede_dict(
        comment.query.filter(comment.article_id.in_(post_ids), comment.author != g.current_user).   # 得到用户所有文章的所有他人评论
            order_by(comment.mark_read, comment.timestamp.desc()),                                  # 将评论按未读->已读、时间倒序排序
        page, per_page, 'user.get_received_comments', id=id)
    mark = request.args.get('mark')
    if mark == 'true':           # 字符串形式
        pagi['has_new'] = False
        que.last_received_comments_read_time = datetime.utcnow()
        que.add_notification('new_received_comment', 0)
        for item in pagi['items']:
                item['is_new'] = False
    else:
        last_read_time = g.current_user.last_received_comments_read_time or datetime(1900, 1, 1)
        for item in pagi['items']:
            if item['timestamp'] > last_read_time:               # 当前评论时间戳大于上次查看时间，说明是新评论
                item['is_new'] = True
                pagi['has_new'] = True
    db.session.commit()
    return jsonify(pagi)








