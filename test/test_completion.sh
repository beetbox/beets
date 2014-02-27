#!/bin/bash

. /etc/bash_completion

initcli() {
  COMP_WORDS=( "beet" "$@" )
  let COMP_CWORD=${#COMP_WORDS[@]}-1
  _beet
}

completes() {
  for word in "$@"; do
    [[ " ${COMPREPLY[@]} " == *[[:space:]]$word[[:space:]]* ]] || return 1
  done
}

COMMANDS='fields import list update remove
          stats version modify move write
          help'

HELP_OPTS='-h --help'


test_commands() {
  initcli '' &&
  completes $COMMANDS &&

  initcli -v '' &&
  completes $COMMANDS &&

  initcli -l help '' &&
  completes $COMMANDS &&

  initcli -d list '' &&
  completes $COMMANDS &&

  initcli -h '' &&
  completes $COMMANDS &&
  true
}

test_command_aliases() {
  initcli ls &&
  completes list &&

  initcli l &&
  ! completes ls &&

  initcli im &&
  completes import &&
  true
}

test_global_opts() {
  initcli - &&
  completes \
    -l --library \
    -d --directory \
    -h --help \
    -c --config \
    -v --verbose &&
  true
}


test_global_file_opts() {
  initcli --library '' &&
  completes $(compgen -f) &&

  initcli -l '' &&
  completes $(compgen -f) &&

  initcli --config '' &&
  completes $(compgen -f) &&

  initcli -c '' &&
  completes $(compgen -f) &&
  true
}


test_global_dir_opts() {
  initcli --directory '' &&
  completes $(compgen -d) &&

  initcli -d '' &&
  completes $(compgen -d) &&
  true
}


test_fields_command() {
  initcli fields - &&
  completes -h --help &&

  initcli fields '' &&
  completes $(compgen -f) &&
  true
}


test_import_files() {
  initcli import '' &&
  completes $(compgen -f) &&

  initcli import --copy -P '' &&
  completes $(compgen -f) &&

  initcli import --log '' &&
  completes $(compgen -f) &&
  true
}


test_import_options() {
  initcli imp -
  completes \
    -h --help \
    -c --copy -C --nocopy \
    -w --write -W --nowrite \
    -a --autotag -A --noautotag \
    -p --resume -P --noresume \
    -l --log --flat
}


test_list_options() {
  initcli list -
  completes \
    -h --help \
    -a --album \
    -p --path
}

test_help_command() {
  initcli help '' &&
  completes $COMMANDS &&
  true
}

run_tests() {
  local tests=$(set | \
    grep --extended-regexp --only-matching '^test_[a-zA-Z_]* \(\) $' |\
    grep --extended-regexp --only-matching '[a-zA-Z_]*'
  )
  local fail=0

  if  [[ -n $@ ]]; then
    tests="$@"
  fi

  for t in $tests; do
    $t || { fail=1 && echo "$t failed" >&2; }
  done
  return $fail
}

run_tests "$@" && echo "completion tests passed"
