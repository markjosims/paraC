from flask import Blueprint, render_template, request, jsonify

from src.parser import parse_word
from src.search import search_word
from src.fst_helpers import get_gloss_str_from_dict

bp = Blueprint('parser', __name__)


@bp.route('/')
def index():
    return render_template('parser.html')


@bp.route('/parse', methods=['POST'])
def parse():
    data = request.get_json()
    word = data.get('word', '').strip()
    fuzzy = data.get('fuzzy', False)

    if not word:
        return jsonify({'error': 'Word is required'}), 400

    try:
        if fuzzy:
            results = search_word(word)
            formatted = []
            for parse in results:
                gloss_str = get_gloss_str_from_dict(parse, include_form=True, verbose=False)
                formatted.append({
                    'gloss': gloss_str,
                    'weight': parse.get('weight', 0),
                    'details': parse
                })
        else:
            results = parse_word(word)
            formatted = []
            for parse in results:
                gloss_str = get_gloss_str_from_dict(parse, include_form=True, verbose=False)
                formatted.append({
                    'gloss': gloss_str,
                    'weight': parse.get('weight', 0),
                    'details': parse
                })

        return jsonify({'results': formatted})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
