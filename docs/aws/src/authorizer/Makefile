# Ο build host είναι x86_64 χωρίς Docker, ο runtime arm64: το pip πρέπει να
# κατεβάσει ρητά aarch64 wheels, αλλιώς το cryptography σπάει στο Lambda.
build-AuthorizerFunction:
	python3 -m pip install -r requirements.txt \
	    --platform manylinux2014_aarch64 \
	    --implementation cp --python-version 3.12 \
	    --only-binary=:all: --upgrade \
	    --target "$(ARTIFACTS_DIR)"
	cp authorizer.py "$(ARTIFACTS_DIR)"
