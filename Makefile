.NOTPARALLEL:
.PHONY: test build

test:
	python3 -B -m unittest discover -s tests -v
	mkdir -p .build
	clang -std=c11 -Wall -Wextra -Werror mute-on-lid-close/test-lid-state.c -o .build/test-lid-state
	.build/test-lid-state

build:
	mkdir -p .build
	clang -std=c11 -Wall -Wextra -Werror -O2 -mmacosx-version-min=12.0 mute-on-lid-close/mute-on-lid-close.c -framework CoreAudio -framework CoreFoundation -framework IOKit -o .build/mute-on-lid-close
