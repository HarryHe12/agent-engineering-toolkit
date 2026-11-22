from app.shared.labels import normalize_label


def show(label):
    return "Item: " + normalize_label(label)
