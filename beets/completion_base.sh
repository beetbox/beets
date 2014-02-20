# This file is part of beets.
# Copyright (c) 2014, Thomas Scholtes.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.



# Completion for the `beet` command
# =================================
#
# Load this script to complete beets subcommands, global options, and
# subcommand options.
#
# If a beets command is found on the command line it completes filenames and
# the subcommand's options. Otherwise it will complete global options and
# subcommands. If the previous option on the command line expects an argument,
# it also completes filenames or directories.  Options are only
# completed if '-' has already been typed on the command line.
#
# Note that completion only works for builtin commands and *not* for
# commands provided by plugins.
#
# Currently, only Bash 4.1 and newer is supported.
#
# TODO
# ----
#
# * Complete arguments for the `--format` option by expanding field variables.
#
#     beet ls -f "$tit[TAB]
#     beet ls -f "$title
#
# * Complete queries.
#
#     beet ls art[TAB]
#     beet ls artist:
#
# * Complete plugin commands by dynamically checking which commands are
#   available.
#
# * Support long options with `=`, e.g. `--config=file`. Debian's bash
#   completion package can handle this.
# 
# * Support for Bash 3.2
#


# Main entry point for completion
_beet() {
  local cur prev commands
  local -A flags opts aliases

  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  _beet_setup

  # Look for the beets subcommand
  local arg cmd=
  for (( i=1; i < COMP_CWORD; i++ )); do
      arg="${COMP_WORDS[i]}"
      if _list_include_item "${opts[_global]}" $arg; then
        ((i++))
      elif [[ "$arg" != -* ]]; then
        cmd="$arg"
        break
      fi
  done

  # Replace command shortcuts
  if [[ -n $cmd && -n ${aliases[$cmd]} ]]; then
    cmd=${aliases[$cmd]}
  fi

  case $cmd in
    "")
      _beet_complete_global
      ;;
    help)
      COMPREPLY+=( $(compgen -W "$commands" -- $cur) )
      ;;
    *)
      _beet_complete $cmd
      ;;
  esac
}
complete -o filenames -F _beet beet


# Adds option and file completion to COMPREPLY for the subcommand $1
_beet_complete() {
  if [[ $cur == -* ]]; then
    local completions="${flags[_common]} ${opts[$1]} ${flags[$1]}"
    COMPREPLY+=( $(compgen -W "$completions"  -- $cur) )
  else
    COMPREPLY+=( $(compgen -f -- $cur) )
  fi
}


# Add global options and commands to the completion
_beet_complete_global() {
  case $prev in
    -h|--help)
      # Complete commands
      COMPREPLY+=( $(compgen -W "$commands" -- $cur) )
      return
      ;;
    -l|--library|-c|--config)
      # Filename completion
      COMPREPLY+=( $(compgen -f $cur))
      return
      ;;
    -d|--directory)
      # Directory completion
      COMPREPLY+=( $(compgen -d $cur))
      return
      ;;
  esac

  if [[ $cur == -* ]]; then
    local completions="${opts[_global]} ${flags[_global]}"
    COMPREPLY+=( $(compgen -W "$completions" -- $cur) )
  elif [[ -n $cur && -n "${aliases[$cur]}" ]]; then
    COMPREPLY+=( ${aliases[$cur]} )
  else
    COMPREPLY+=( $(compgen -W "$commands" -- $cur) )
  fi
}

# Returns true if the space separated list $1 includes $2
_list_include_item() {
  [[ $1 =~ (^|[[:space:]])"$2"($|[[:space:]]) ]]
}

# This is where beets dynamically adds the _beet_setup function. This
# function sets the variables $flags, $opts, $commands, and $aliases.
