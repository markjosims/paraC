import flask
from flask import Flask, render_template, request
from src.forms import (
    parse_inflected_verb,
    inflect_verb_with_features,
    get_inflected_paradigm_for_verb,
    FV_CLASSES
)
from src.lexicon import get_all_verb_data
from src.constants import VERB_FEATURE_VALUES
from src.sentences import get_elan_analyses
import pynini
from unicodedata import normalize

app = Flask(__name__)

TEMPLATE_DEFAULTS = {
    "feature_options": VERB_FEATURE_VALUES,
    "fv_classes": FV_CLASSES,
    "verb_lexicon": get_all_verb_data(),
}

@app.route('/', methods=['GET', 'POST'])
def index():
    """Renders the main page."""
    mode = request.args.get('mode', 'default')
    context = {'mode': mode, 'inflect_input': {}, 'parse_input': ''}

    if request.method == 'POST':
        if 'submit_parse' in request.form and mode == 'test':
            result = handle_test_parse(request.form)
        elif 'submit_parse' in request.form:
            result = handle_parse(request.form)
        elif 'submit_inflect' in request.form and mode == 'test':
            result = handle_test_inflect(request.form)
        elif 'submit_inflect' in request.form:
            result = handle_inflect(request.form)
        context.update(result)

    return render_template("index.html", **TEMPLATE_DEFAULTS, **context)

def handle_parse(form):
    """Handles the parsing form submission."""
    normalize_parse_input = lambda s: normalize("NFKD", s).replace('-', '')
    parse_input = form.get('parse_input', '')
    parse_input = normalize_parse_input(parse_input)

    fv_class = form.get('fv_class')
    if not parse_input:
        result = {"error": "Please enter a verb form."}
    else:
        result = parse_inflected_verb(parse_input, fv_class)
    result['form']=parse_input

    return {'parse_result': result}

def handle_test_parse(form):
    parse_input = form.get('parse_input', '').strip()
    verb_row = form.get('verb_root', '')
    verb_root, fv, gloss = verb_row.split()

    expected = {
        'tam': form.get('tam'),
        'deixis': form.get('deixis'),
        'class': form.get('class'),
        'root': verb_root,
        'gloss': gloss,
    }
    actual = parse_inflected_verb(parse_input, fv)
    actual_filtered = {key: actual.get(key) for key in expected.keys()}
    
    if actual_filtered == expected:
        status = "Success"
    else:
        status = "Failure"

    return {
        "test_parse_result": {
            "status": status,
            "expected": expected,
            "actual": actual,
        },
        "parse_input": parse_input,
    }

def handle_inflect(form):
    """Handles the inflection form submission."""
    verb_row = form.get('verb_root', '')
    verb_root, fv, _ = verb_row.split()
    features = {
        'tam': form.get('tam'),
        'deixis': form.get('deixis'),
        'class': form.get('class')
    }
    
    if not verb_root:
        result = "Please enter a verb root."
    else:
        try:
            result = inflect_verb_with_features(verb_root, fv, features)
        except:
            result = "Invalid feature combination."

    return {
        'inflect_result': result,
        'inflect_input': {
            'verb_root': verb_row,
            **features,
        }
    }

def handle_test_inflect(form):
    verb_row = form.get('verb_root', '')
    verb_root, fv, _ = verb_row.split()
    features = {
        'tam': form.get('tam'),
        'deixis': form.get('deixis'),
        'class': form.get('class')
    }
    normalize_inflect_input = lambda s: normalize("NFKD", s)
    expected = form.get('expected_inflected_form', '').strip()
    expected = normalize_inflect_input(expected)

    actual = inflect_verb_with_features(verb_root, fv, features)

    if actual == expected:
        status = "Success"
    else:
        status = "Failure"
    
    return {
        'test_inflect_result': {
            "status": status,
            "expected": expected,
            "actual": actual,
        },
        'inflect_input': {
            'verb_root': verb_row,
            **features,
        },
        'expected_inflected_form': expected,
    }

@app.route('/lexicon')
def lexicon_page():
    """
    Handles the lexicon page.
    Fetches all verb data and displays it in a table.
    """
    return render_template('lexicon.html', **TEMPLATE_DEFAULTS)

@app.route('/paradigms', methods=['GET', 'POST'])
def paradigms_page():
    context = {'paradigm': None, 'inflect_input': None}
    if request.method == 'POST':
        verb_row = request.form.get('verb_root', '')
        verb_root, fv, _ = verb_row.split()
        context['paradigm']=get_inflected_paradigm_for_verb(verb_root, fv)
        context['inflect_input']=verb_row
    return render_template('paradigms.html', **TEMPLATE_DEFAULTS, **context)

@app.route('/sentences')
def sentences_page():
    """
    Handles the sentences page,
    displaying sentences from the database.
    """
    sentences_data = get_elan_analyses()
    return render_template('sentences.html', sentences=sentences_data)

if __name__ == '__main__':
    app.run(debug=True)