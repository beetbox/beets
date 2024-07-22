
# An 'argparse' description for global options for 'beet'.
function __fish_beet_global_optspec
    string join \n v/verbose h/help c/config= l/library= d/directory= \
        format-item= format-album=
end

# Test for a (particular) 'beet' subcommand in the command-line buffer.
function __fish_beet_subcommand
    set -l cmd (commandline -opc)
    set -e cmd[1]
    set -l test_cmd $argv[1]

    set -f cached $__fish_beet_subcommand_cache
    set -l crange "1 .. $(count $cached)"
    if not set -q __fish_beet_subcommand_cache
        or test "$cmd[$crange]" != "$cached"

        argparse --stop-nonopt (__fish_beet_global_optspec) -- $cmd
        or return 1

        set -q _flag_help; and return 1
        test (count $argv) -eq 0; and return 1

        set -l crange "1 .. -$(count $argv)"
        set -g __fish_beet_subcommand_cache $cmd[$crange]
        set -f cached $__fish_beet_subcommand_cache
    end 2>/dev/null

    if test -n "$test_cmd"
        test "$test_cmd" = "$cached[-1]"
    else
        test (count $cached) -gt 0
    end
end

# Test for a '<field>:<value>' argument in the command-line buffer.
function __fish_beet_metadata_param
    set -l cmd (commandline -ct)
    set -l field (string split -f 1 -- ":" $cmd)
    or return 1

    if test -n "$argv[1]"
        test "$field" = "$argv[1]"
    else
        return 0
    end
end
complete -c beet -f
complete -c beet -n not\ __fish_beet_subcommand -s l -l library -F -d the\ library\ database\ file -r
complete -c beet -n not\ __fish_beet_subcommand -s d -l directory -F -d the\ music\ directory -r
complete -c beet -n not\ __fish_beet_subcommand -s v -l verbose -f -d print\ debugging\ information
complete -c beet -n not\ __fish_beet_subcommand -s h -l help -f -d print\ a\ help\ message
complete -c beet -n not\ __fish_beet_subcommand -s c -l config -F -d the\ configuration\ file\ to\ use -r
complete -c beet -n not\ __fish_beet_subcommand -l format-item -f -d print\ with\ custom\ format
complete -c beet -n not\ __fish_beet_subcommand -l format-album -f -d print\ with\ custom\ format
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ fields\) -d show\ fields\ available\ for\ queries\ and\ format\ strings -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ help\ \\\?\) -d give\ detailed\ help\ on\ a\ specific\ sub-command -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ import\ imp\ im\) -d import\ new\ music -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ list\ ls\) -d query\ the\ library -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ update\ upd\ up\) -d update\ the\ library -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ remove\ rm\) -d remove\ matching\ items\ from\ the\ library -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ stats\) -d show\ statistics\ about\ the\ library\ or\ a\ query -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ version\) -d output\ version\ information -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ modify\ mod\) -d change\ metadata\ fields -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ move\ mv\) -d move\ or\ copy\ items -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ write\) -d write\ tag\ information\ to\ files -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ config\) -d show\ or\ edit\ the\ user\ configuration -r
complete -c beet -n not\ __fish_beet_subcommand -f -a \(string\ split\ \'\ \'\ --\ completion\) -d print\ shell\ script\ that\ provides\ command\ line\ completion -r
set __fish_beet_flds acoustid_fingerprint: acoustid_id: added: album: album_id: albumartist: albumartist_credit: albumartist_sort: albumartists: albumartists_credit: albumartists_sort: albumdisambig: albumstatus: albumtotal: albumtype: albumtypes: arranger: artist: artist_credit: artist_sort: artists: artists_credit: artists_ids: artists_sort: artpath: asin: barcode: bitdepth: bitrate: bitrate_mode: bpm: catalognum: channels: comments: comp: composer: composer_sort: country: day: disc: discogs_albumid: discogs_artistid: discogs_labelid: disctitle: disctotal: encoder: encoder_info: encoder_settings: filesize: format: genre: grouping: id: initial_key: isrc: label: language: length: lyricist: lyrics: mb_albumartistid: mb_albumartistids: mb_albumid: mb_artistid: mb_artistids: mb_releasegroupid: mb_releasetrackid: mb_trackid: mb_workid: media: month: mtime: original_day: original_month: original_year: path: r128_album_gain: r128_track_gain: release_group_title: releasegroupdisambig: remixer: rg_album_gain: rg_album_peak: rg_track_gain: rg_track_peak: samplerate: script: singleton: style: title: track: trackdisambig: tracktotal: work: work_disambig: year:
complete -c beet -n __fish_beet_subcommand -n not\ __fish_beet_metadata_param -f -a \$__fish_beet_flds -d known\ metadata\ field -r
