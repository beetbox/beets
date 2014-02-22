import os.path

def completion_script(commands):
    base_script = os.path.join(os.path.dirname(__file__), 'completion_base.sh')
    for line in  open(base_script, 'r'):
        yield line

    options = {}
    aliases = {}
    command_names = []

    # Collect subcommands
    for cmd in commands:
        name = cmd.name
        command_names.append(name)

        for alias in cmd.aliases:
            aliases[alias] = name

        options[name] = {'flags': [], 'opts': []}
        for opts in cmd.parser._get_all_options()[1:]:
            if opts.action in ('store_true', 'store_false'):
                option_type = 'flags'
            else:
                option_type = 'opts'

            options[name][option_type].extend(opts._short_opts + opts._long_opts)

    # Add global options
    options['_global'] = {
        'flags': ['-v', '--verbose'],
        'opts': '-l --library -c --config -d --directory -h --help'.split(' ')
    }

    # Help subcommand
    command_names.append('help')

    # Add flags common to all commands
    options['_common'] = {
        'flags': ['-h', '--help']
    }

    # Start generating the script
    yield "_beet() {\n"
    yield "  local commands='%s'\n" % ' '.join(command_names)
    yield "\n"

    yield "  local aliases='%s'\n" % ' '.join(aliases.keys())
    for alias, cmd in aliases.items():
        yield "  local alias__%s=%s\n" % (alias, cmd)
    yield '\n'

    for cmd, opts in options.items():
        for option_type, option_list in opts.items():
            if option_list:
                option_list = ' '.join(option_list)
                yield "  local %s__%s='%s'\n" % (option_type, cmd, option_list)
    yield '  _beet_dispatch\n'
    yield '}\n'
