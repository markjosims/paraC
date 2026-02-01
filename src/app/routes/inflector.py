from flask import Blueprint, render_template, request, jsonify

from src.parser import inflect_word
from src.app.utils import get_pos_features

bp = Blueprint('inflector', __name__)


@bp.route('/')
def index():
    pos_features = get_pos_features()
    return render_template('inflector.html', pos_features=pos_features)


@bp.route('/inflect', methods=['POST'])
def inflect():
    data = request.get_json()
    root = data.get('root', '').strip()
    pos = data.get('part_of_speech', '')

    if not root:
        return jsonify({'error': 'Root is required'}), 400
    if not pos:
        return jsonify({'error': 'Part of speech is required'}), 400

    feature_dict = {k: v for k, v in data.items() if k not in ('root',) and v and v != 'unmarked'}

    try:
        results = inflect_word(root=root, **feature_dict)
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
