from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("campus_hub/index.html")

@app.route("/campus-hub")
def campus_hub():
    return render_template("campus_hub/index.html")

if __name__ == "__main__":
    app.run(debug=True)