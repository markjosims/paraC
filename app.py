import flask
from flask import Flask, render_template, request
from src.forms import parse_inflected_verb, inflect_verb_with_features, FV_CLASSES
from src.lexicon import get_all_verb_data
from src.constants import VERB_FEATURE_VALUES
import pynini

app = Flask(__name__)

TEMPLATE_DEFAULTS = {
    "feature_options": VERB_FEATURE_VALUES,
    "fv_classes": FV_CLASSES,
    "verb_lexicon": get_all_verb_data(),
}

@app.route('/', methods=['GET', 'POST'])
def index():
    """Renders the main page."""
    parse_input = ""
    parse_result = None
    inflect_input = {}
    inflect_result = ""

    if request.method == 'POST':
        if 'submit_parse' in request.form:
            parse_result = handle_parse(request.form)

        elif 'submit_inflect' in request.form:
            inflect_result, verb_row, features = handle_inflect(request.form)
            inflect_input = {"verb_root": verb_row, **features}

    form_state = {
        "parse_input": parse_input,
        "parse_result": parse_result,
        "inflect_result": inflect_result,
        "inflect_input": inflect_input,
    }

    return render_template("index.html", **TEMPLATE_DEFAULTS, **form_state)

def handle_parse(form):
    """Handles the parsing form submission."""
    inflected_form = form.get('inflected_form', '')
    fv_class = form.get('fv_class')
    if not inflected_form:
        result = {"error": "Please enter a verb form."}
    else:
        result = parse_inflected_verb(inflected_form, fv_class)
    result['form']=inflected_form
    return result

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

    return result, verb_row, features

@app.route('/lexicon')
def lexicon_page():
    """
    Handles the lexicon page.
    Fetches all verb data and displays it in a table.
    """
    return render_template('lexicon.html', **TEMPLATE_DEFAULTS)

if __name__ == '__main__':
    app.run(debug=True)