(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);throw new Error("Cannot find module '"+o+"'")}var f=n[o]={exports:{}};t[o][0].call(f.exports,function(e){var n=t[o][1][e];return s(n?n:e)},f,f.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
exports.MP3Demuxer = require('./src/demuxer');
exports.MP3Decoder = require('./src/decoder');

},{"./src/decoder":2,"./src/demuxer":3}],2:[function(require,module,exports){
var AV = (window.AV);
var MP3FrameHeader = require('./header');
var MP3Stream = require('./stream');
var MP3Frame = require('./frame');
var MP3Synth = require('./synth');
var Layer1 = require('./layer1');
var Layer2 = require('./layer2');
var Layer3 = require('./layer3');

var MP3Decoder = AV.Decoder.extend(function() {
    AV.Decoder.register('mp3', this);
    
    this.prototype.init = function() {
        this.mp3_stream = new MP3Stream(this.bitstream);
        this.frame = new MP3Frame();
        this.synth = new MP3Synth();
        this.seeking = false;
    };
    
    this.prototype.readChunk = function() {
        var stream = this.mp3_stream;
        var frame = this.frame;
        var synth = this.synth;

        // if we just seeked, we may start getting errors involving the frame reservoir,
        // so keep going until we successfully decode a frame
        if (this.seeking) {
            while (true) {
                try {
                    frame.decode(stream);
                    break;
                } catch (err) {
                    if (err instanceof AV.UnderflowError)
                        throw err;
                }
            }
            
            this.seeking = false;
        } else {
            frame.decode(stream);
        }
        
        synth.frame(frame);
        
        // interleave samples
        var data = synth.pcm.samples,
            channels = synth.pcm.channels,
            len = synth.pcm.length,
            output = new Float32Array(len * channels),
            j = 0;
        
        for (var k = 0; k < len; k++) {
            for (var i = 0; i < channels; i++) {
                output[j++] = data[i][k];
            }
        }
        
        return output;
    };
    
    this.prototype.seek = function(timestamp) {
        var offset;
        
        // if there was a Xing or VBRI tag with a seek table, use that
        // otherwise guesstimate based on CBR bitrate
        if (this.demuxer.seekPoints.length > 0) {
            timestamp = this._super(timestamp);
            offset = this.stream.offset;
        } else {
            offset = timestamp * this.format.bitrate / 8 / this.format.sampleRate;
        }
        
        this.mp3_stream.reset(offset);
        
        // try to find 3 consecutive valid frame headers in a row
        for (var i = 0; i < 4096; i++) {
            var pos = offset + i;
            for (var j = 0; j < 3; j++) {
                this.mp3_stream.reset(pos);
                
                try {
                    var header = MP3FrameHeader.decode(this.mp3_stream);
                } catch (e) {
                    break;
                }
                
                // skip the rest of the frame
                var size = header.framesize();
                if (size == null)
                    break;
                        
                pos += size;
            }
            
            // check if we're done
            if (j === 3)
                break;
        }
        
        // if we didn't find 3 frames, just try the first one and hope for the best
        if (j !== 3)
            i = 0;
            
        this.mp3_stream.reset(offset + i);
        
        // if we guesstimated, update the timestamp to another estimate of where we actually seeked to
        if (this.demuxer.seekPoints.length === 0)
            timestamp = this.stream.offset / (this.format.bitrate / 8) * this.format.sampleRate;
        
        this.seeking = true;
        return timestamp;
    };
});

module.exports = MP3Decoder;

},{"./frame":4,"./header":5,"./layer1":9,"./layer2":10,"./layer3":11,"./stream":12,"./synth":13}],3:[function(require,module,exports){
var AV = (window.AV);
var ID3v23Stream = require('./id3').ID3v23Stream;
var ID3v22Stream = require('./id3').ID3v22Stream;
var MP3FrameHeader = require('./header');
var MP3Stream = require('./stream');

var MP3Demuxer = AV.Demuxer.extend(function() {
    AV.Demuxer.register(this);
    
    this.probe = function(stream) {
        var off = stream.offset;
        
        // skip id3 metadata if it exists
        var id3header = MP3Demuxer.getID3v2Header(stream);
        if (id3header)
            stream.advance(10 + id3header.length);
        
        // attempt to read the header of the first audio frame
        var s = new MP3Stream(new AV.Bitstream(stream));
        var header = null;
        
        try {
            header = MP3FrameHeader.decode(s);
        } catch (e) {};
        
        // go back to the beginning, for other probes
        stream.seek(off);
        
        return !!header;
    };
    
    this.getID3v2Header = function(stream) {
        if (stream.peekString(0, 3) == 'ID3') {
            stream = AV.Stream.fromBuffer(stream.peekBuffer(0, 10));
            stream.advance(3); // 'ID3'

            var major = stream.readUInt8();
            var minor = stream.readUInt8();
            var flags = stream.readUInt8();
            var bytes = stream.readBuffer(4).data;
            var length = (bytes[0] << 21) | (bytes[1] << 14) | (bytes[2] << 7) | bytes[3];

            return { 
                version: '2.' + major + '.' + minor, 
                major: major, 
                minor: minor, 
                flags: flags, 
                length: length 
            };
        }
        
        return null;
    };
    
    const XING_OFFSETS = [[32, 17], [17, 9]];
    this.prototype.parseDuration = function(header) {
        var stream = this.stream;
        var frames;
                
        var offset = stream.offset;
        if (!header || header.layer !== 3)
            return false;
        
        // Check for Xing/Info tag
        stream.advance(XING_OFFSETS[header.flags & MP3FrameHeader.FLAGS.LSF_EXT ? 1 : 0][header.nchannels() === 1 ? 1 : 0]);
        var tag = stream.readString(4);
        if (tag === 'Xing' || tag === 'Info') {
            var flags = stream.readUInt32();
            if (flags & 1) 
                frames = stream.readUInt32();
                
            if (flags & 2)
                var size = stream.readUInt32();
                
            if (flags & 4 && frames && size) {
                for (var i = 0; i < 100; i++) {
                    var b = stream.readUInt8();
                    var pos = b / 256 * size | 0;
                    var time = i / 100 * (frames * header.nbsamples() * 32) | 0;
                    this.addSeekPoint(pos, time);
                }
            }
                
            if (flags & 8)
                stream.advance(4);
                
        } else {
            // Check for VBRI tag (always 32 bytes after end of mpegaudio header)
            stream.seek(offset + 4 + 32);
            tag = stream.readString(4);
            if (tag == 'VBRI' && stream.readUInt16() === 1) { // Check tag version
                stream.advance(4); // skip delay and quality
                stream.advance(4); // skip size
                frames = stream.readUInt32();
                
                var entries = stream.readUInt16();
                var scale = stream.readUInt16();
                var bytesPerEntry = stream.readUInt16();
                var framesPerEntry = stream.readUInt16();
                var fn = 'readUInt' + (bytesPerEntry * 8);
                
                var pos = 0;
                for (var i = 0; i < entries; i++) {
                    this.addSeekPoint(pos, framesPerEntry * i);
                    pos += stream[fn]();
                }
            }
        }
        
        if (!frames)
            return false;
            
        this.emit('duration', (frames * header.nbsamples() * 32) / header.samplerate * 1000 | 0);
        return true;
    };
    
    this.prototype.readChunk = function() {
        var stream = this.stream;
        
        if (!this.sentInfo) {
            // read id3 metadata if it exists
            var id3header = MP3Demuxer.getID3v2Header(stream);
            if (id3header) {
                stream.advance(10);
                
                if (id3header.major > 2) {
                    var id3 = new ID3v23Stream(id3header, stream);
                } else {
                    var id3 = new ID3v22Stream(id3header, stream);
                }
                
                this.emit('metadata', id3.read());
            }
            
            // read the header of the first audio frame
            var off = stream.offset;
            var s = new MP3Stream(new AV.Bitstream(stream));
            
            var header = MP3FrameHeader.decode(s);
            if (!header)
                return this.emit('error', 'Could not find first frame.');
            
            this.emit('format', {
                formatID: 'mp3',
                sampleRate: header.samplerate,
                channelsPerFrame: header.nchannels(),
                bitrate: header.bitrate,
                floatingPoint: true
            });
            
            var sentDuration = this.parseDuration(header);
            stream.advance(off - stream.offset);
            
            // if there were no Xing/VBRI tags, guesstimate the duration based on data size and bitrate
            this.dataSize = 0;
            if (!sentDuration) {
                this.on('end', function() {
                    this.emit('duration', this.dataSize * 8 / header.bitrate * 1000 | 0);
                });
            }
            
            this.sentInfo = true;
        }
        
        while (stream.available(1)) {
            var buffer = stream.readSingleBuffer(stream.remainingBytes());
            this.dataSize += buffer.length;
            this.emit('data', buffer);
        }
    };
});

module.exports = MP3Demuxer;

},{"./header":5,"./id3":7,"./stream":12}],4:[function(require,module,exports){
var MP3FrameHeader = require('./header');
var utils = require('./utils');

function MP3Frame() {
    this.header = null;                     // MPEG audio header
    this.options = 0;                       // decoding options (from stream)
    this.sbsample = utils.makeArray([2, 36, 32]); // synthesis subband filter samples
    this.overlap = utils.makeArray([2, 32, 18]);  // Layer III block overlap data
    this.decoders = [];
}

// included layer decoders are registered here
MP3Frame.layers = [];

MP3Frame.prototype.decode = function(stream) {
    if (!this.header || !(this.header.flags & MP3FrameHeader.FLAGS.INCOMPLETE))
        this.header = MP3FrameHeader.decode(stream);

    this.header.flags &= ~MP3FrameHeader.FLAGS.INCOMPLETE;
    
    // make an instance of the decoder for this layer if needed
    var decoder = this.decoders[this.header.layer - 1];
    if (!decoder) {
        var Layer = MP3Frame.layers[this.header.layer];
        if (!Layer)
            throw new Error("Layer " + this.header.layer + " is not supported.");
            
        decoder = this.decoders[this.header.layer - 1] = new Layer();
    }
    
    decoder.decode(stream, this);
};

module.exports = MP3Frame;

},{"./header":5,"./utils":15}],5:[function(require,module,exports){
var AV = (window.AV);

function MP3FrameHeader() {
    this.layer          = 0; // audio layer (1, 2, or 3)
    this.mode           = 0; // channel mode (see above)
    this.mode_extension = 0; // additional mode info
    this.emphasis       = 0; // de-emphasis to use (see above)

    this.bitrate        = 0; // stream bitrate (bps)
    this.samplerate     = 0; // sampling frequency (Hz)

    this.crc_check      = 0; // frame CRC accumulator
    this.crc_target     = 0; // final target CRC checksum

    this.flags          = 0; // flags (see above)
    this.private_bits   = 0; // private bits
}

const BITRATES = [
    // MPEG-1
    [ 0,  32000,  64000,  96000, 128000, 160000, 192000, 224000,  // Layer I
         256000, 288000, 320000, 352000, 384000, 416000, 448000 ],
    [ 0,  32000,  48000,  56000,  64000,  80000,  96000, 112000,  // Layer II
         128000, 160000, 192000, 224000, 256000, 320000, 384000 ],
    [ 0,  32000,  40000,  48000,  56000,  64000,  80000,  96000,  // Layer III
         112000, 128000, 160000, 192000, 224000, 256000, 320000 ],

    // MPEG-2 LSF
    [ 0,  32000,  48000,  56000,  64000,  80000,  96000, 112000,  // Layer I
         128000, 144000, 160000, 176000, 192000, 224000, 256000 ],
    [ 0,   8000,  16000,  24000,  32000,  40000,  48000,  56000,  // Layers
          64000,  80000,  96000, 112000, 128000, 144000, 160000 ] // II & III
];

const SAMPLERATES = [ 
    44100, 48000, 32000 
];

MP3FrameHeader.FLAGS = {
    NPRIVATE_III: 0x0007,   // number of Layer III private bits
    INCOMPLETE  : 0x0008,   // header but not data is decoded

    PROTECTION  : 0x0010,   // frame has CRC protection
    COPYRIGHT   : 0x0020,   // frame is copyright
    ORIGINAL    : 0x0040,   // frame is original (else copy)
    PADDING     : 0x0080,   // frame has additional slot

    I_STEREO    : 0x0100,   // uses intensity joint stereo
    MS_STEREO   : 0x0200,   // uses middle/side joint stereo
    FREEFORMAT  : 0x0400,   // uses free format bitrate

    LSF_EXT     : 0x1000,   // lower sampling freq. extension
    MC_EXT      : 0x2000,   // multichannel audio extension
    MPEG_2_5_EXT: 0x4000    // MPEG 2.5 (unofficial) extension
};

const PRIVATE = {
    HEADER  : 0x0100, // header private bit
    III     : 0x001f  // Layer III private bits (up to 5)
};

MP3FrameHeader.MODE = {
    SINGLE_CHANNEL: 0, // single channel
    DUAL_CHANNEL  : 1, // dual channel
    JOINT_STEREO  : 2, // joint (MS/intensity) stereo
    STEREO        : 3  // normal LR stereo
};

const EMPHASIS = {
    NONE      : 0, // no emphasis
    _50_15_US : 1, // 50/15 microseconds emphasis
    CCITT_J_17: 3, // CCITT J.17 emphasis
    RESERVED  : 2  // unknown emphasis
};

MP3FrameHeader.BUFFER_GUARD = 8;
MP3FrameHeader.BUFFER_MDLEN = (511 + 2048 + MP3FrameHeader.BUFFER_GUARD);

MP3FrameHeader.prototype.copy = function() {
    var clone = new MP3FrameHeader();
    var keys = Object.keys(this);
    
    for (var key in keys) {
        clone[key] = this[key];
    }
    
    return clone;
}

MP3FrameHeader.prototype.nchannels = function () {
    return this.mode === 0 ? 1 : 2;
};

MP3FrameHeader.prototype.nbsamples = function() {
    return (this.layer === 1 ? 12 : ((this.layer === 3 && (this.flags & MP3FrameHeader.FLAGS.LSF_EXT)) ? 18 : 36));
};

MP3FrameHeader.prototype.framesize = function() {
    if (this.bitrate === 0)
        return null;
    
    var padding = (this.flags & MP3FrameHeader.FLAGS.PADDING ? 1 : 0);
    switch (this.layer) {
        case 1:
            var size = (this.bitrate * 12) / this.samplerate | 0;
            return (size + padding) * 4;
            
        case 2:
            var size = (this.bitrate * 144) / this.samplerate | 0;
            return size + padding;
            
        case 3:
        default:
            var lsf = this.flags & MP3FrameHeader.FLAGS.LSF_EXT ? 1 : 0;
            var size = (this.bitrate * 144) / (this.samplerate << lsf) | 0;
            return size + padding;
    }
};

MP3FrameHeader.prototype.decode = function(stream) {
    this.flags        = 0;
    this.private_bits = 0;
    
    // syncword 
    stream.advance(11);

    // MPEG 2.5 indicator (really part of syncword) 
    if (stream.read(1) === 0)
        this.flags |= MP3FrameHeader.FLAGS.MPEG_2_5_EXT;

    // ID 
    if (stream.read(1) === 0) {
        this.flags |= MP3FrameHeader.FLAGS.LSF_EXT;
    } else if (this.flags & MP3FrameHeader.FLAGS.MPEG_2_5_EXT) {
        throw new AV.UnderflowError(); // LOSTSYNC
    }

    // layer 
    this.layer = 4 - stream.read(2);

    if (this.layer === 4)
        throw new Error('Invalid layer');

    // protection_bit 
    if (stream.read(1) === 0)
        this.flags |= MP3FrameHeader.FLAGS.PROTECTION;

    // bitrate_index 
    var index = stream.read(4);
    if (index === 15)
        throw new Error('Invalid bitrate');

    if (this.flags & MP3FrameHeader.FLAGS.LSF_EXT) {
        this.bitrate = BITRATES[3 + (this.layer >> 1)][index];
    } else {
        this.bitrate = BITRATES[this.layer - 1][index];
    }

    // sampling_frequency 
    index = stream.read(2);
    if (index === 3)
        throw new Error('Invalid sampling frequency');

    this.samplerate = SAMPLERATES[index];

    if (this.flags & MP3FrameHeader.FLAGS.LSF_EXT) {
        this.samplerate /= 2;

        if (this.flags & MP3FrameHeader.FLAGS.MPEG_2_5_EXT)
            this.samplerate /= 2;
    }

    // padding_bit 
    if (stream.read(1))
        this.flags |= MP3FrameHeader.FLAGS.PADDING;

    // private_bit 
    if (stream.read(1))
        this.private_bits |= PRIVATE.HEADER;

    // mode 
    this.mode = 3 - stream.read(2);

    // mode_extension 
    this.mode_extension = stream.read(2);

    // copyright 
    if (stream.read(1))
        this.flags |= MP3FrameHeader.FLAGS.COPYRIGHT;

    // original/copy 
    if (stream.read(1))
        this.flags |= MP3FrameHeader.FLAGS.ORIGINAL;

    // emphasis 
    this.emphasis = stream.read(2);

    // crc_check 
    if (this.flags & MP3FrameHeader.FLAGS.PROTECTION)
        this.crc_target = stream.read(16);
};

MP3FrameHeader.decode = function(stream) {
    // synchronize
    var ptr = stream.next_frame;
    var syncing = true;
    var header = null;
    
    while (syncing) {
        syncing = false;
        
        if (stream.sync) {
            if (!stream.available(MP3FrameHeader.BUFFER_GUARD)) {
                stream.next_frame = ptr;
                throw new AV.UnderflowError();
            } else if (!(stream.getU8(ptr) === 0xff && (stream.getU8(ptr + 1) & 0xe0) === 0xe0)) {
                // mark point where frame sync word was expected
                stream.this_frame = ptr;
                stream.next_frame = ptr + 1;
                throw new AV.UnderflowError(); // LOSTSYNC
            }
        } else {
            stream.seek(ptr * 8);
            if (!stream.doSync())
                throw new AV.UnderflowError();
                
            ptr = stream.nextByte();
        }
        
        // begin processing
        stream.this_frame = ptr;
        stream.next_frame = ptr + 1; // possibly bogus sync word
        
        stream.seek(stream.this_frame * 8);
        
        header = new MP3FrameHeader();
        header.decode(stream);
        
        if (header.bitrate === 0) {
            if (stream.freerate === 0 || !stream.sync || (header.layer === 3 && stream.freerate > 640000))
                MP3FrameHeader.free_bitrate(stream, header);
            
            header.bitrate = stream.freerate;
            header.flags |= MP3FrameHeader.FLAGS.FREEFORMAT;
        }
        
        // calculate beginning of next frame
        var pad_slot = (header.flags & MP3FrameHeader.FLAGS.PADDING) ? 1 : 0;
        
        if (header.layer === 1) {
            var N = (((12 * header.bitrate / header.samplerate) << 0) + pad_slot) * 4;
        } else {
            var slots_per_frame = (header.layer === 3 && (header.flags & MP3FrameHeader.FLAGS.LSF_EXT)) ? 72 : 144;
            var N = ((slots_per_frame * header.bitrate / header.samplerate) << 0) + pad_slot;
        }
        
        // verify there is enough data left in buffer to decode this frame
        if (!stream.available(N + MP3FrameHeader.BUFFER_GUARD)) {
            stream.next_frame = stream.this_frame;
            throw new AV.UnderflowError();
        }
        
        stream.next_frame = stream.this_frame + N;
        
        if (!stream.sync) {
            // check that a valid frame header follows this frame
            ptr = stream.next_frame;
            
            if (!(stream.getU8(ptr) === 0xff && (stream.getU8(ptr + 1) & 0xe0) === 0xe0)) {
                ptr = stream.next_frame = stream.this_frame + 1;

                // emulating 'goto sync'
                syncing = true;
                continue;
            }
            
            stream.sync = true;
        }
    }
    
    header.flags |= MP3FrameHeader.FLAGS.INCOMPLETE;
    return header;
};

MP3FrameHeader.free_bitrate = function(stream, header) {
    var pad_slot = header.flags & MP3FrameHeader.FLAGS.PADDING ? 1 : 0,
        slots_per_frame = header.layer === 3 && header.flags & MP3FrameHeader.FLAGS.LSF_EXT ? 72 : 144;
    
    var start = stream.offset();
    var rate = 0;
        
    while (stream.doSync()) {
        var peek_header = header.copy();
        var peek_stream = stream.copy();
        
        if (peek_header.decode(peek_stream) && peek_header.layer === header.layer && peek_header.samplerate === header.samplerate) {
            var N = stream.nextByte() - stream.this_frame;
            
            if (header.layer === 1) {
                rate = header.samplerate * (N - 4 * pad_slot + 4) / 48 / 1000 | 0;
            } else {
                rate = header.samplerate * (N - pad_slot + 1) / slots_per_frame / 1000 | 0;
            }
            
            if (rate >= 8)
                break;
        }
        
        stream.advance(8);
    }
    
    stream.seek(start);
    
    if (rate < 8 || (header.layer === 3 && rate > 640))
        throw new AV.UnderflowError(); // LOSTSYNC
    
    stream.freerate = rate * 1000;
};

module.exports = MP3FrameHeader;

},{}],6:[function(require,module,exports){
/*
 * These are the Huffman code words for Layer III.
 * The data for these tables are derived from Table B.7 of ISO/IEC 11172-3.
 *
 * These tables support decoding up to 4 Huffman code bits at a time.
 */

var PTR = function(offs, bits) {
    return {
        final: 0,
        ptr: {
            bits:   bits,
            offset: offs
        }
    };
};

var huffquad_V = function (v, w, x, y, hlen) {
    return {
        final: 1,
        value: {
            v: v,
            w: w,
            x: x,
            y: y,
            hlen: hlen
        }
    };
};

const hufftabA = [
  /* 0000 */ PTR(16, 2),
  /* 0001 */ PTR(20, 2),
  /* 0010 */ PTR(24, 1),
  /* 0011 */ PTR(26, 1),
  /* 0100 */ huffquad_V(0, 0, 1, 0, 4),
  /* 0101 */ huffquad_V(0, 0, 0, 1, 4),
  /* 0110 */ huffquad_V(0, 1, 0, 0, 4),
  /* 0111 */ huffquad_V(1, 0, 0, 0, 4),
  /* 1000 */ huffquad_V(0, 0, 0, 0, 1),
  /* 1001 */ huffquad_V(0, 0, 0, 0, 1),
  /* 1010 */ huffquad_V(0, 0, 0, 0, 1),
  /* 1011 */ huffquad_V(0, 0, 0, 0, 1),
  /* 1100 */ huffquad_V(0, 0, 0, 0, 1),
  /* 1101 */ huffquad_V(0, 0, 0, 0, 1),
  /* 1110 */ huffquad_V(0, 0, 0, 0, 1),
  /* 1111 */ huffquad_V(0, 0, 0, 0, 1),

  /* 0000 ... */
  /* 00   */ huffquad_V(1, 0, 1, 1, 2),	/* 16 */
  /* 01   */ huffquad_V(1, 1, 1, 1, 2),
  /* 10   */ huffquad_V(1, 1, 0, 1, 2),
  /* 11   */ huffquad_V(1, 1, 1, 0, 2),

  /* 0001 ... */
  /* 00   */ huffquad_V(0, 1, 1, 1, 2),	/* 20 */
  /* 01   */ huffquad_V(0, 1, 0, 1, 2),
  /* 10   */ huffquad_V(1, 0, 0, 1, 1),
  /* 11   */ huffquad_V(1, 0, 0, 1, 1),

  /* 0010 ... */
  /* 0    */ huffquad_V(0, 1, 1, 0, 1),	/* 24 */
  /* 1    */ huffquad_V(0, 0, 1, 1, 1),

  /* 0011 ... */
  /* 0    */ huffquad_V(1, 0, 1, 0, 1),	/* 26 */
  /* 1    */ huffquad_V(1, 1, 0, 0, 1)
];

const hufftabB = [
  /* 0000 */ huffquad_V(1, 1, 1, 1, 4),
  /* 0001 */ huffquad_V(1, 1, 1, 0, 4),
  /* 0010 */ huffquad_V(1, 1, 0, 1, 4),
  /* 0011 */ huffquad_V(1, 1, 0, 0, 4),
  /* 0100 */ huffquad_V(1, 0, 1, 1, 4),
  /* 0101 */ huffquad_V(1, 0, 1, 0, 4),
  /* 0110 */ huffquad_V(1, 0, 0, 1, 4),
  /* 0111 */ huffquad_V(1, 0, 0, 0, 4),
  /* 1000 */ huffquad_V(0, 1, 1, 1, 4),
  /* 1001 */ huffquad_V(0, 1, 1, 0, 4),
  /* 1010 */ huffquad_V(0, 1, 0, 1, 4),
  /* 1011 */ huffquad_V(0, 1, 0, 0, 4),
  /* 1100 */ huffquad_V(0, 0, 1, 1, 4),
  /* 1101 */ huffquad_V(0, 0, 1, 0, 4),
  /* 1110 */ huffquad_V(0, 0, 0, 1, 4),
  /* 1111 */ huffquad_V(0, 0, 0, 0, 4)
];

var V = function (x, y, hlen) {
    return {
        final: 1,
        value: {
            x: x,
            y: y,
            hlen: hlen
        }
    };
};

const hufftab0 = [
  /*      */ V(0, 0, 0)
];

const hufftab1 = [
  /* 000  */ V(1, 1, 3),
  /* 001  */ V(0, 1, 3),
  /* 010  */ V(1, 0, 2),
  /* 011  */ V(1, 0, 2),
  /* 100  */ V(0, 0, 1),
  /* 101  */ V(0, 0, 1),
  /* 110  */ V(0, 0, 1),
  /* 111  */ V(0, 0, 1)
];

const hufftab2 = [
  /* 000  */ PTR(8, 3),
  /* 001  */ V(1, 1, 3),
  /* 010  */ V(0, 1, 3),
  /* 011  */ V(1, 0, 3),
  /* 100  */ V(0, 0, 1),
  /* 101  */ V(0, 0, 1),
  /* 110  */ V(0, 0, 1),
  /* 111  */ V(0, 0, 1),

  /* 000 ... */
  /* 000  */ V(2, 2, 3),	/* 8 */
  /* 001  */ V(0, 2, 3),
  /* 010  */ V(1, 2, 2),
  /* 011  */ V(1, 2, 2),
  /* 100  */ V(2, 1, 2),
  /* 101  */ V(2, 1, 2),
  /* 110  */ V(2, 0, 2),
  /* 111  */ V(2, 0, 2)
];

const hufftab3 = [
  /* 000  */ PTR(8, 3),
  /* 001  */ V(1, 0, 3),
  /* 010  */ V(1, 1, 2),
  /* 011  */ V(1, 1, 2),
  /* 100  */ V(0, 1, 2),
  /* 101  */ V(0, 1, 2),
  /* 110  */ V(0, 0, 2),
  /* 111  */ V(0, 0, 2),

  /* 000 ... */
  /* 000  */ V(2, 2, 3),	/* 8 */
  /* 001  */ V(0, 2, 3),
  /* 010  */ V(1, 2, 2),
  /* 011  */ V(1, 2, 2),
  /* 100  */ V(2, 1, 2),
  /* 101  */ V(2, 1, 2),
  /* 110  */ V(2, 0, 2),
  /* 111  */ V(2, 0, 2)
];

const hufftab5 = [
  /* 000  */ PTR(8, 4),
  /* 001  */ V(1, 1, 3),
  /* 010  */ V(0, 1, 3),
  /* 011  */ V(1, 0, 3),
  /* 100  */ V(0, 0, 1),
  /* 101  */ V(0, 0, 1),
  /* 110  */ V(0, 0, 1),
  /* 111  */ V(0, 0, 1),

  /* 000 ... */
  /* 0000 */ PTR(24, 1),	/* 8 */
  /* 0001 */ V(3, 2, 4),
  /* 0010 */ V(3, 1, 3),
  /* 0011 */ V(3, 1, 3),
  /* 0100 */ V(1, 3, 4),
  /* 0101 */ V(0, 3, 4),
  /* 0110 */ V(3, 0, 4),
  /* 0111 */ V(2, 2, 4),
  /* 1000 */ V(1, 2, 3),
  /* 1001 */ V(1, 2, 3),
  /* 1010 */ V(2, 1, 3),
  /* 1011 */ V(2, 1, 3),
  /* 1100 */ V(0, 2, 3),
  /* 1101 */ V(0, 2, 3),
  /* 1110 */ V(2, 0, 3),
  /* 1111 */ V(2, 0, 3),

  /* 000 0000 ... */
  /* 0    */ V(3, 3, 1),	/* 24 */
  /* 1    */ V(2, 3, 1)
];

const hufftab6 = [
  /* 0000 */ PTR(16, 3),
  /* 0001 */ PTR(24, 1),
  /* 0010 */ PTR(26, 1),
  /* 0011 */ V(1, 2, 4),
  /* 0100 */ V(2, 1, 4),
  /* 0101 */ V(2, 0, 4),
  /* 0110 */ V(0, 1, 3),
  /* 0111 */ V(0, 1, 3),
  /* 1000 */ V(1, 1, 2),
  /* 1001 */ V(1, 1, 2),
  /* 1010 */ V(1, 1, 2),
  /* 1011 */ V(1, 1, 2),
  /* 1100 */ V(1, 0, 3),
  /* 1101 */ V(1, 0, 3),
  /* 1110 */ V(0, 0, 3),
  /* 1111 */ V(0, 0, 3),

  /* 0000 ... */
  /* 000  */ V(3, 3, 3),	/* 16 */
  /* 001  */ V(0, 3, 3),
  /* 010  */ V(2, 3, 2),
  /* 011  */ V(2, 3, 2),
  /* 100  */ V(3, 2, 2),
  /* 101  */ V(3, 2, 2),
  /* 110  */ V(3, 0, 2),
  /* 111  */ V(3, 0, 2),

  /* 0001 ... */
  /* 0    */ V(1, 3, 1),	/* 24 */
  /* 1    */ V(3, 1, 1),

  /* 0010 ... */
  /* 0    */ V(2, 2, 1),	/* 26 */
  /* 1    */ V(0, 2, 1)
];

const hufftab7 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 2),
  /* 0011 */ V(1, 1, 4),
  /* 0100 */ V(0, 1, 3),
  /* 0101 */ V(0, 1, 3),
  /* 0110 */ V(1, 0, 3),
  /* 0111 */ V(1, 0, 3),
  /* 1000 */ V(0, 0, 1),
  /* 1001 */ V(0, 0, 1),
  /* 1010 */ V(0, 0, 1),
  /* 1011 */ V(0, 0, 1),
  /* 1100 */ V(0, 0, 1),
  /* 1101 */ V(0, 0, 1),
  /* 1110 */ V(0, 0, 1),
  /* 1111 */ V(0, 0, 1),

  /* 0000 ... */
  /* 0000 */ PTR(52, 2),	/* 16 */
  /* 0001 */ PTR(56, 1),
  /* 0010 */ PTR(58, 1),
  /* 0011 */ V(1, 5, 4),
  /* 0100 */ V(5, 1, 4),
  /* 0101 */ PTR(60, 1),
  /* 0110 */ V(5, 0, 4),
  /* 0111 */ PTR(62, 1),
  /* 1000 */ V(2, 4, 4),
  /* 1001 */ V(4, 2, 4),
  /* 1010 */ V(1, 4, 3),
  /* 1011 */ V(1, 4, 3),
  /* 1100 */ V(4, 1, 3),
  /* 1101 */ V(4, 1, 3),
  /* 1110 */ V(4, 0, 3),
  /* 1111 */ V(4, 0, 3),

  /* 0001 ... */
  /* 0000 */ V(0, 4, 4),	/* 32 */
  /* 0001 */ V(2, 3, 4),
  /* 0010 */ V(3, 2, 4),
  /* 0011 */ V(0, 3, 4),
  /* 0100 */ V(1, 3, 3),
  /* 0101 */ V(1, 3, 3),
  /* 0110 */ V(3, 1, 3),
  /* 0111 */ V(3, 1, 3),
  /* 1000 */ V(3, 0, 3),
  /* 1001 */ V(3, 0, 3),
  /* 1010 */ V(2, 2, 3),
  /* 1011 */ V(2, 2, 3),
  /* 1100 */ V(1, 2, 2),
  /* 1101 */ V(1, 2, 2),
  /* 1110 */ V(1, 2, 2),
  /* 1111 */ V(1, 2, 2),

  /* 0010 ... */
  /* 00   */ V(2, 1, 1),	/* 48 */
  /* 01   */ V(2, 1, 1),
  /* 10   */ V(0, 2, 2),
  /* 11   */ V(2, 0, 2),

  /* 0000 0000 ... */
  /* 00   */ V(5, 5, 2),	/* 52 */
  /* 01   */ V(4, 5, 2),
  /* 10   */ V(5, 4, 2),
  /* 11   */ V(5, 3, 2),

  /* 0000 0001 ... */
  /* 0    */ V(3, 5, 1),	/* 56 */
  /* 1    */ V(4, 4, 1),

  /* 0000 0010 ... */
  /* 0    */ V(2, 5, 1),	/* 58 */
  /* 1    */ V(5, 2, 1),

  /* 0000 0101 ... */
  /* 0    */ V(0, 5, 1),	/* 60 */
  /* 1    */ V(3, 4, 1),

  /* 0000 0111 ... */
  /* 0    */ V(4, 3, 1),	/* 62 */
  /* 1    */ V(3, 3, 1)
];

const hufftab8 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ V(1, 2, 4),
  /* 0011 */ V(2, 1, 4),
  /* 0100 */ V(1, 1, 2),
  /* 0101 */ V(1, 1, 2),
  /* 0110 */ V(1, 1, 2),
  /* 0111 */ V(1, 1, 2),
  /* 1000 */ V(0, 1, 3),
  /* 1001 */ V(0, 1, 3),
  /* 1010 */ V(1, 0, 3),
  /* 1011 */ V(1, 0, 3),
  /* 1100 */ V(0, 0, 2),
  /* 1101 */ V(0, 0, 2),
  /* 1110 */ V(0, 0, 2),
  /* 1111 */ V(0, 0, 2),

  /* 0000 ... */
  /* 0000 */ PTR(48, 3),	/* 16 */
  /* 0001 */ PTR(56, 2),
  /* 0010 */ PTR(60, 1),
  /* 0011 */ V(1, 5, 4),
  /* 0100 */ V(5, 1, 4),
  /* 0101 */ PTR(62, 1),
  /* 0110 */ PTR(64, 1),
  /* 0111 */ V(2, 4, 4),
  /* 1000 */ V(4, 2, 4),
  /* 1001 */ V(1, 4, 4),
  /* 1010 */ V(4, 1, 3),
  /* 1011 */ V(4, 1, 3),
  /* 1100 */ V(0, 4, 4),
  /* 1101 */ V(4, 0, 4),
  /* 1110 */ V(2, 3, 4),
  /* 1111 */ V(3, 2, 4),

  /* 0001 ... */
  /* 0000 */ V(1, 3, 4),	/* 32 */
  /* 0001 */ V(3, 1, 4),
  /* 0010 */ V(0, 3, 4),
  /* 0011 */ V(3, 0, 4),
  /* 0100 */ V(2, 2, 2),
  /* 0101 */ V(2, 2, 2),
  /* 0110 */ V(2, 2, 2),
  /* 0111 */ V(2, 2, 2),
  /* 1000 */ V(0, 2, 2),
  /* 1001 */ V(0, 2, 2),
  /* 1010 */ V(0, 2, 2),
  /* 1011 */ V(0, 2, 2),
  /* 1100 */ V(2, 0, 2),
  /* 1101 */ V(2, 0, 2),
  /* 1110 */ V(2, 0, 2),
  /* 1111 */ V(2, 0, 2),

  /* 0000 0000 ... */
  /* 000  */ V(5, 5, 3),	/* 48 */
  /* 001  */ V(5, 4, 3),
  /* 010  */ V(4, 5, 2),
  /* 011  */ V(4, 5, 2),
  /* 100  */ V(5, 3, 1),
  /* 101  */ V(5, 3, 1),
  /* 110  */ V(5, 3, 1),
  /* 111  */ V(5, 3, 1),

  /* 0000 0001 ... */
  /* 00   */ V(3, 5, 2),	/* 56 */
  /* 01   */ V(4, 4, 2),
  /* 10   */ V(2, 5, 1),
  /* 11   */ V(2, 5, 1),

  /* 0000 0010 ... */
  /* 0    */ V(5, 2, 1),	/* 60 */
  /* 1    */ V(0, 5, 1),

  /* 0000 0101 ... */
  /* 0    */ V(3, 4, 1),	/* 62 */
  /* 1    */ V(4, 3, 1),

  /* 0000 0110 ... */
  /* 0    */ V(5, 0, 1),	/* 64 */
  /* 1    */ V(3, 3, 1)
];

const hufftab9 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 3),
  /* 0010 */ PTR(40, 2),
  /* 0011 */ PTR(44, 2),
  /* 0100 */ PTR(48, 1),
  /* 0101 */ V(1, 2, 4),
  /* 0110 */ V(2, 1, 4),
  /* 0111 */ V(2, 0, 4),
  /* 1000 */ V(1, 1, 3),
  /* 1001 */ V(1, 1, 3),
  /* 1010 */ V(0, 1, 3),
  /* 1011 */ V(0, 1, 3),
  /* 1100 */ V(1, 0, 3),
  /* 1101 */ V(1, 0, 3),
  /* 1110 */ V(0, 0, 3),
  /* 1111 */ V(0, 0, 3),

  /* 0000 ... */
  /* 0000 */ PTR(50, 1),	/* 16 */
  /* 0001 */ V(3, 5, 4),
  /* 0010 */ V(5, 3, 4),
  /* 0011 */ PTR(52, 1),
  /* 0100 */ V(4, 4, 4),
  /* 0101 */ V(2, 5, 4),
  /* 0110 */ V(5, 2, 4),
  /* 0111 */ V(1, 5, 4),
  /* 1000 */ V(5, 1, 3),
  /* 1001 */ V(5, 1, 3),
  /* 1010 */ V(3, 4, 3),
  /* 1011 */ V(3, 4, 3),
  /* 1100 */ V(4, 3, 3),
  /* 1101 */ V(4, 3, 3),
  /* 1110 */ V(5, 0, 4),
  /* 1111 */ V(0, 4, 4),

  /* 0001 ... */
  /* 000  */ V(2, 4, 3),	/* 32 */
  /* 001  */ V(4, 2, 3),
  /* 010  */ V(3, 3, 3),
  /* 011  */ V(4, 0, 3),
  /* 100  */ V(1, 4, 2),
  /* 101  */ V(1, 4, 2),
  /* 110  */ V(4, 1, 2),
  /* 111  */ V(4, 1, 2),

  /* 0010 ... */
  /* 00   */ V(2, 3, 2),	/* 40 */
  /* 01   */ V(3, 2, 2),
  /* 10   */ V(1, 3, 1),
  /* 11   */ V(1, 3, 1),

  /* 0011 ... */
  /* 00   */ V(3, 1, 1),	/* 44 */
  /* 01   */ V(3, 1, 1),
  /* 10   */ V(0, 3, 2),
  /* 11   */ V(3, 0, 2),

  /* 0100 ... */
  /* 0    */ V(2, 2, 1),	/* 48 */
  /* 1    */ V(0, 2, 1),

  /* 0000 0000 ... */
  /* 0    */ V(5, 5, 1),	/* 50 */
  /* 1    */ V(4, 5, 1),

  /* 0000 0011 ... */
  /* 0    */ V(5, 4, 1),	/* 52 */
  /* 1    */ V(0, 5, 1)
];

const hufftab10 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 2),
  /* 0011 */ V(1, 1, 4),
  /* 0100 */ V(0, 1, 3),
  /* 0101 */ V(0, 1, 3),
  /* 0110 */ V(1, 0, 3),
  /* 0111 */ V(1, 0, 3),
  /* 1000 */ V(0, 0, 1),
  /* 1001 */ V(0, 0, 1),
  /* 1010 */ V(0, 0, 1),
  /* 1011 */ V(0, 0, 1),
  /* 1100 */ V(0, 0, 1),
  /* 1101 */ V(0, 0, 1),
  /* 1110 */ V(0, 0, 1),
  /* 1111 */ V(0, 0, 1),

  /* 0000 ... */
  /* 0000 */ PTR(52, 3),	/* 16 */
  /* 0001 */ PTR(60, 2),
  /* 0010 */ PTR(64, 3),
  /* 0011 */ PTR(72, 1),
  /* 0100 */ PTR(74, 2),
  /* 0101 */ PTR(78, 2),
  /* 0110 */ PTR(82, 2),
  /* 0111 */ V(1, 7, 4),
  /* 1000 */ V(7, 1, 4),
  /* 1001 */ PTR(86, 1),
  /* 1010 */ PTR(88, 2),
  /* 1011 */ PTR(92, 2),
  /* 1100 */ V(1, 6, 4),
  /* 1101 */ V(6, 1, 4),
  /* 1110 */ V(6, 0, 4),
  /* 1111 */ PTR(96, 1),

  /* 0001 ... */
  /* 0000 */ PTR(98, 1),	/* 32 */
  /* 0001 */ PTR(100, 1),
  /* 0010 */ V(1, 4, 4),
  /* 0011 */ V(4, 1, 4),
  /* 0100 */ V(4, 0, 4),
  /* 0101 */ V(2, 3, 4),
  /* 0110 */ V(3, 2, 4),
  /* 0111 */ V(0, 3, 4),
  /* 1000 */ V(1, 3, 3),
  /* 1001 */ V(1, 3, 3),
  /* 1010 */ V(3, 1, 3),
  /* 1011 */ V(3, 1, 3),
  /* 1100 */ V(3, 0, 3),
  /* 1101 */ V(3, 0, 3),
  /* 1110 */ V(2, 2, 3),
  /* 1111 */ V(2, 2, 3),

  /* 0010 ... */
  /* 00   */ V(1, 2, 2),	/* 48 */
  /* 01   */ V(2, 1, 2),
  /* 10   */ V(0, 2, 2),
  /* 11   */ V(2, 0, 2),

  /* 0000 0000 ... */
  /* 000  */ V(7, 7, 3),	/* 52 */
  /* 001  */ V(6, 7, 3),
  /* 010  */ V(7, 6, 3),
  /* 011  */ V(5, 7, 3),
  /* 100  */ V(7, 5, 3),
  /* 101  */ V(6, 6, 3),
  /* 110  */ V(4, 7, 2),
  /* 111  */ V(4, 7, 2),

  /* 0000 0001 ... */
  /* 00   */ V(7, 4, 2),	/* 60 */
  /* 01   */ V(5, 6, 2),
  /* 10   */ V(6, 5, 2),
  /* 11   */ V(3, 7, 2),

  /* 0000 0010 ... */
  /* 000  */ V(7, 3, 2),	/* 64 */
  /* 001  */ V(7, 3, 2),
  /* 010  */ V(4, 6, 2),
  /* 011  */ V(4, 6, 2),
  /* 100  */ V(5, 5, 3),
  /* 101  */ V(5, 4, 3),
  /* 110  */ V(6, 3, 2),
  /* 111  */ V(6, 3, 2),

  /* 0000 0011 ... */
  /* 0    */ V(2, 7, 1),	/* 72 */
  /* 1    */ V(7, 2, 1),

  /* 0000 0100 ... */
  /* 00   */ V(6, 4, 2),	/* 74 */
  /* 01   */ V(0, 7, 2),
  /* 10   */ V(7, 0, 1),
  /* 11   */ V(7, 0, 1),

  /* 0000 0101 ... */
  /* 00   */ V(6, 2, 1),	/* 78 */
  /* 01   */ V(6, 2, 1),
  /* 10   */ V(4, 5, 2),
  /* 11   */ V(3, 5, 2),

  /* 0000 0110 ... */
  /* 00   */ V(0, 6, 1),	/* 82 */
  /* 01   */ V(0, 6, 1),
  /* 10   */ V(5, 3, 2),
  /* 11   */ V(4, 4, 2),

  /* 0000 1001 ... */
  /* 0    */ V(3, 6, 1),	/* 86 */
  /* 1    */ V(2, 6, 1),

  /* 0000 1010 ... */
  /* 00   */ V(2, 5, 2),	/* 88 */
  /* 01   */ V(5, 2, 2),
  /* 10   */ V(1, 5, 1),
  /* 11   */ V(1, 5, 1),

  /* 0000 1011 ... */
  /* 00   */ V(5, 1, 1),	/* 92 */
  /* 01   */ V(5, 1, 1),
  /* 10   */ V(3, 4, 2),
  /* 11   */ V(4, 3, 2),

  /* 0000 1111 ... */
  /* 0    */ V(0, 5, 1),	/* 96 */
  /* 1    */ V(5, 0, 1),

  /* 0001 0000 ... */
  /* 0    */ V(2, 4, 1),	/* 98 */
  /* 1    */ V(4, 2, 1),

  /* 0001 0001 ... */
  /* 0    */ V(3, 3, 1),	/* 100 */
  /* 1    */ V(0, 4, 1)
];

const hufftab11 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 4),
  /* 0011 */ PTR(64, 3),
  /* 0100 */ V(1, 2, 4),
  /* 0101 */ PTR(72, 1),
  /* 0110 */ V(1, 1, 3),
  /* 0111 */ V(1, 1, 3),
  /* 1000 */ V(0, 1, 3),
  /* 1001 */ V(0, 1, 3),
  /* 1010 */ V(1, 0, 3),
  /* 1011 */ V(1, 0, 3),
  /* 1100 */ V(0, 0, 2),
  /* 1101 */ V(0, 0, 2),
  /* 1110 */ V(0, 0, 2),
  /* 1111 */ V(0, 0, 2),

  /* 0000 ... */
  /* 0000 */ PTR(74, 2),	/* 16 */
  /* 0001 */ PTR(78, 3),
  /* 0010 */ PTR(86, 2),
  /* 0011 */ PTR(90, 1),
  /* 0100 */ PTR(92, 2),
  /* 0101 */ V(2, 7, 4),
  /* 0110 */ V(7, 2, 4),
  /* 0111 */ PTR(96, 1),
  /* 1000 */ V(7, 1, 3),
  /* 1001 */ V(7, 1, 3),
  /* 1010 */ V(1, 7, 4),
  /* 1011 */ V(7, 0, 4),
  /* 1100 */ V(3, 6, 4),
  /* 1101 */ V(6, 3, 4),
  /* 1110 */ V(6, 0, 4),
  /* 1111 */ PTR(98, 1),

  /* 0001 ... */
  /* 0000 */ PTR(100, 1),	/* 32 */
  /* 0001 */ V(1, 5, 4),
  /* 0010 */ V(6, 2, 3),
  /* 0011 */ V(6, 2, 3),
  /* 0100 */ V(2, 6, 4),
  /* 0101 */ V(0, 6, 4),
  /* 0110 */ V(1, 6, 3),
  /* 0111 */ V(1, 6, 3),
  /* 1000 */ V(6, 1, 3),
  /* 1001 */ V(6, 1, 3),
  /* 1010 */ V(5, 1, 4),
  /* 1011 */ V(3, 4, 4),
  /* 1100 */ V(5, 0, 4),
  /* 1101 */ PTR(102, 1),
  /* 1110 */ V(2, 4, 4),
  /* 1111 */ V(4, 2, 4),

  /* 0010 ... */
  /* 0000 */ V(1, 4, 4),	/* 48 */
  /* 0001 */ V(4, 1, 4),
  /* 0010 */ V(0, 4, 4),
  /* 0011 */ V(4, 0, 4),
  /* 0100 */ V(2, 3, 3),
  /* 0101 */ V(2, 3, 3),
  /* 0110 */ V(3, 2, 3),
  /* 0111 */ V(3, 2, 3),
  /* 1000 */ V(1, 3, 2),
  /* 1001 */ V(1, 3, 2),
  /* 1010 */ V(1, 3, 2),
  /* 1011 */ V(1, 3, 2),
  /* 1100 */ V(3, 1, 2),
  /* 1101 */ V(3, 1, 2),
  /* 1110 */ V(3, 1, 2),
  /* 1111 */ V(3, 1, 2),

  /* 0011 ... */
  /* 000  */ V(0, 3, 3),	/* 64 */
  /* 001  */ V(3, 0, 3),
  /* 010  */ V(2, 2, 2),
  /* 011  */ V(2, 2, 2),
  /* 100  */ V(2, 1, 1),
  /* 101  */ V(2, 1, 1),
  /* 110  */ V(2, 1, 1),
  /* 111  */ V(2, 1, 1),

  /* 0101 ... */
  /* 0    */ V(0, 2, 1),	/* 72 */
  /* 1    */ V(2, 0, 1),

  /* 0000 0000 ... */
  /* 00   */ V(7, 7, 2),	/* 74 */
  /* 01   */ V(6, 7, 2),
  /* 10   */ V(7, 6, 2),
  /* 11   */ V(7, 5, 2),

  /* 0000 0001 ... */
  /* 000  */ V(6, 6, 2),	/* 78 */
  /* 001  */ V(6, 6, 2),
  /* 010  */ V(4, 7, 2),
  /* 011  */ V(4, 7, 2),
  /* 100  */ V(7, 4, 2),
  /* 101  */ V(7, 4, 2),
  /* 110  */ V(5, 7, 3),
  /* 111  */ V(5, 5, 3),

  /* 0000 0010 ... */
  /* 00   */ V(5, 6, 2),	/* 86 */
  /* 01   */ V(6, 5, 2),
  /* 10   */ V(3, 7, 1),
  /* 11   */ V(3, 7, 1),

  /* 0000 0011 ... */
  /* 0    */ V(7, 3, 1),	/* 90 */
  /* 1    */ V(4, 6, 1),

  /* 0000 0100 ... */
  /* 00   */ V(4, 5, 2),	/* 92 */
  /* 01   */ V(5, 4, 2),
  /* 10   */ V(3, 5, 2),
  /* 11   */ V(5, 3, 2),

  /* 0000 0111 ... */
  /* 0    */ V(6, 4, 1),	/* 96 */
  /* 1    */ V(0, 7, 1),

  /* 0000 1111 ... */
  /* 0    */ V(4, 4, 1),	/* 98 */
  /* 1    */ V(2, 5, 1),

  /* 0001 0000 ... */
  /* 0    */ V(5, 2, 1),	/* 100 */
  /* 1    */ V(0, 5, 1),

  /* 0001 1101 ... */
  /* 0    */ V(4, 3, 1),	/* 102 */
  /* 1    */ V(3, 3, 1)
];

const hufftab12 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 4),
  /* 0011 */ PTR(64, 2),
  /* 0100 */ PTR(68, 3),
  /* 0101 */ PTR(76, 1),
  /* 0110 */ V(1, 2, 4),
  /* 0111 */ V(2, 1, 4),
  /* 1000 */ PTR(78, 1),
  /* 1001 */ V(0, 0, 4),
  /* 1010 */ V(1, 1, 3),
  /* 1011 */ V(1, 1, 3),
  /* 1100 */ V(0, 1, 3),
  /* 1101 */ V(0, 1, 3),
  /* 1110 */ V(1, 0, 3),
  /* 1111 */ V(1, 0, 3),

  /* 0000 ... */
  /* 0000 */ PTR(80, 2),	/* 16 */
  /* 0001 */ PTR(84, 1),
  /* 0010 */ PTR(86, 1),
  /* 0011 */ PTR(88, 1),
  /* 0100 */ V(5, 6, 4),
  /* 0101 */ V(3, 7, 4),
  /* 0110 */ PTR(90, 1),
  /* 0111 */ V(2, 7, 4),
  /* 1000 */ V(7, 2, 4),
  /* 1001 */ V(4, 6, 4),
  /* 1010 */ V(6, 4, 4),
  /* 1011 */ V(1, 7, 4),
  /* 1100 */ V(7, 1, 4),
  /* 1101 */ PTR(92, 1),
  /* 1110 */ V(3, 6, 4),
  /* 1111 */ V(6, 3, 4),

  /* 0001 ... */
  /* 0000 */ V(4, 5, 4),	/* 32 */
  /* 0001 */ V(5, 4, 4),
  /* 0010 */ V(4, 4, 4),
  /* 0011 */ PTR(94, 1),
  /* 0100 */ V(2, 6, 3),
  /* 0101 */ V(2, 6, 3),
  /* 0110 */ V(6, 2, 3),
  /* 0111 */ V(6, 2, 3),
  /* 1000 */ V(6, 1, 3),
  /* 1001 */ V(6, 1, 3),
  /* 1010 */ V(1, 6, 4),
  /* 1011 */ V(6, 0, 4),
  /* 1100 */ V(3, 5, 4),
  /* 1101 */ V(5, 3, 4),
  /* 1110 */ V(2, 5, 4),
  /* 1111 */ V(5, 2, 4),

  /* 0010 ... */
  /* 0000 */ V(1, 5, 3),	/* 48 */
  /* 0001 */ V(1, 5, 3),
  /* 0010 */ V(5, 1, 3),
  /* 0011 */ V(5, 1, 3),
  /* 0100 */ V(3, 4, 3),
  /* 0101 */ V(3, 4, 3),
  /* 0110 */ V(4, 3, 3),
  /* 0111 */ V(4, 3, 3),
  /* 1000 */ V(5, 0, 4),
  /* 1001 */ V(0, 4, 4),
  /* 1010 */ V(2, 4, 3),
  /* 1011 */ V(2, 4, 3),
  /* 1100 */ V(4, 2, 3),
  /* 1101 */ V(4, 2, 3),
  /* 1110 */ V(1, 4, 3),
  /* 1111 */ V(1, 4, 3),

  /* 0011 ... */
  /* 00   */ V(3, 3, 2),	/* 64 */
  /* 01   */ V(4, 1, 2),
  /* 10   */ V(2, 3, 2),
  /* 11   */ V(3, 2, 2),

  /* 0100 ... */
  /* 000  */ V(4, 0, 3),	/* 68 */
  /* 001  */ V(0, 3, 3),
  /* 010  */ V(3, 0, 2),
  /* 011  */ V(3, 0, 2),
  /* 100  */ V(1, 3, 1),
  /* 101  */ V(1, 3, 1),
  /* 110  */ V(1, 3, 1),
  /* 111  */ V(1, 3, 1),

  /* 0101 ... */
  /* 0    */ V(3, 1, 1),	/* 76 */
  /* 1    */ V(2, 2, 1),

  /* 1000 ... */
  /* 0    */ V(0, 2, 1),	/* 78 */
  /* 1    */ V(2, 0, 1),

  /* 0000 0000 ... */
  /* 00   */ V(7, 7, 2),	/* 80 */
  /* 01   */ V(6, 7, 2),
  /* 10   */ V(7, 6, 1),
  /* 11   */ V(7, 6, 1),

  /* 0000 0001 ... */
  /* 0    */ V(5, 7, 1),	/* 84 */
  /* 1    */ V(7, 5, 1),

  /* 0000 0010 ... */
  /* 0    */ V(6, 6, 1),	/* 86 */
  /* 1    */ V(4, 7, 1),

  /* 0000 0011 ... */
  /* 0    */ V(7, 4, 1),	/* 88 */
  /* 1    */ V(6, 5, 1),

  /* 0000 0110 ... */
  /* 0    */ V(7, 3, 1),	/* 90 */
  /* 1    */ V(5, 5, 1),

  /* 0000 1101 ... */
  /* 0    */ V(0, 7, 1),	/* 92 */
  /* 1    */ V(7, 0, 1),

  /* 0001 0011 ... */
  /* 0    */ V(0, 6, 1),	/* 94 */
  /* 1    */ V(0, 5, 1)
];

const hufftab13 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 4),
  /* 0011 */ PTR(64, 2),
  /* 0100 */ V(1, 1, 4),
  /* 0101 */ V(0, 1, 4),
  /* 0110 */ V(1, 0, 3),
  /* 0111 */ V(1, 0, 3),
  /* 1000 */ V(0, 0, 1),
  /* 1001 */ V(0, 0, 1),
  /* 1010 */ V(0, 0, 1),
  /* 1011 */ V(0, 0, 1),
  /* 1100 */ V(0, 0, 1),
  /* 1101 */ V(0, 0, 1),
  /* 1110 */ V(0, 0, 1),
  /* 1111 */ V(0, 0, 1),

  /* 0000 ... */
  /* 0000 */ PTR(68, 4),	/* 16 */
  /* 0001 */ PTR(84, 4),
  /* 0010 */ PTR(100, 4),
  /* 0011 */ PTR(116, 4),
  /* 0100 */ PTR(132, 4),
  /* 0101 */ PTR(148, 4),
  /* 0110 */ PTR(164, 3),
  /* 0111 */ PTR(172, 3),
  /* 1000 */ PTR(180, 3),
  /* 1001 */ PTR(188, 3),
  /* 1010 */ PTR(196, 3),
  /* 1011 */ PTR(204, 3),
  /* 1100 */ PTR(212, 1),
  /* 1101 */ PTR(214, 2),
  /* 1110 */ PTR(218, 3),
  /* 1111 */ PTR(226, 1),

  /* 0001 ... */
  /* 0000 */ PTR(228, 2),	/* 32 */
  /* 0001 */ PTR(232, 2),
  /* 0010 */ PTR(236, 2),
  /* 0011 */ PTR(240, 2),
  /* 0100 */ V(8, 1, 4),
  /* 0101 */ PTR(244, 1),
  /* 0110 */ PTR(246, 1),
  /* 0111 */ PTR(248, 1),
  /* 1000 */ PTR(250, 2),
  /* 1001 */ PTR(254, 1),
  /* 1010 */ V(1, 5, 4),
  /* 1011 */ V(5, 1, 4),
  /* 1100 */ PTR(256, 1),
  /* 1101 */ PTR(258, 1),
  /* 1110 */ PTR(260, 1),
  /* 1111 */ V(1, 4, 4),

  /* 0010 ... */
  /* 0000 */ V(4, 1, 3),	/* 48 */
  /* 0001 */ V(4, 1, 3),
  /* 0010 */ V(0, 4, 4),
  /* 0011 */ V(4, 0, 4),
  /* 0100 */ V(2, 3, 4),
  /* 0101 */ V(3, 2, 4),
  /* 0110 */ V(1, 3, 3),
  /* 0111 */ V(1, 3, 3),
  /* 1000 */ V(3, 1, 3),
  /* 1001 */ V(3, 1, 3),
  /* 1010 */ V(0, 3, 3),
  /* 1011 */ V(0, 3, 3),
  /* 1100 */ V(3, 0, 3),
  /* 1101 */ V(3, 0, 3),
  /* 1110 */ V(2, 2, 3),
  /* 1111 */ V(2, 2, 3),

  /* 0011 ... */
  /* 00   */ V(1, 2, 2),	/* 64 */
  /* 01   */ V(2, 1, 2),
  /* 10   */ V(0, 2, 2),
  /* 11   */ V(2, 0, 2),

  /* 0000 0000 ... */
  /* 0000 */ PTR(262, 4),	/* 68 */
  /* 0001 */ PTR(278, 4),
  /* 0010 */ PTR(294, 4),
  /* 0011 */ PTR(310, 3),
  /* 0100 */ PTR(318, 2),
  /* 0101 */ PTR(322, 2),
  /* 0110 */ PTR(326, 3),
  /* 0111 */ PTR(334, 2),
  /* 1000 */ PTR(338, 1),
  /* 1001 */ PTR(340, 2),
  /* 1010 */ PTR(344, 2),
  /* 1011 */ PTR(348, 2),
  /* 1100 */ PTR(352, 2),
  /* 1101 */ PTR(356, 2),
  /* 1110 */ V(1, 15, 4),
  /* 1111 */ V(15, 1, 4),

  /* 0000 0001 ... */
  /* 0000 */ V(15, 0, 4),	/* 84 */
  /* 0001 */ PTR(360, 1),
  /* 0010 */ PTR(362, 1),
  /* 0011 */ PTR(364, 1),
  /* 0100 */ V(14, 2, 4),
  /* 0101 */ PTR(366, 1),
  /* 0110 */ V(1, 14, 4),
  /* 0111 */ V(14, 1, 4),
  /* 1000 */ PTR(368, 1),
  /* 1001 */ PTR(370, 1),
  /* 1010 */ PTR(372, 1),
  /* 1011 */ PTR(374, 1),
  /* 1100 */ PTR(376, 1),
  /* 1101 */ PTR(378, 1),
  /* 1110 */ V(12, 6, 4),
  /* 1111 */ V(3, 13, 4),

  /* 0000 0010 ... */
  /* 0000 */ PTR(380, 1),	/* 100 */
  /* 0001 */ V(2, 13, 4),
  /* 0010 */ V(13, 2, 4),
  /* 0011 */ V(1, 13, 4),
  /* 0100 */ V(11, 7, 4),
  /* 0101 */ PTR(382, 1),
  /* 0110 */ PTR(384, 1),
  /* 0111 */ V(12, 3, 4),
  /* 1000 */ PTR(386, 1),
  /* 1001 */ V(4, 11, 4),
  /* 1010 */ V(13, 1, 3),
  /* 1011 */ V(13, 1, 3),
  /* 1100 */ V(0, 13, 4),
  /* 1101 */ V(13, 0, 4),
  /* 1110 */ V(8, 10, 4),
  /* 1111 */ V(10, 8, 4),

  /* 0000 0011 ... */
  /* 0000 */ V(4, 12, 4),	/* 116 */
  /* 0001 */ V(12, 4, 4),
  /* 0010 */ V(6, 11, 4),
  /* 0011 */ V(11, 6, 4),
  /* 0100 */ V(3, 12, 3),
  /* 0101 */ V(3, 12, 3),
  /* 0110 */ V(2, 12, 3),
  /* 0111 */ V(2, 12, 3),
  /* 1000 */ V(12, 2, 3),
  /* 1001 */ V(12, 2, 3),
  /* 1010 */ V(5, 11, 3),
  /* 1011 */ V(5, 11, 3),
  /* 1100 */ V(11, 5, 4),
  /* 1101 */ V(8, 9, 4),
  /* 1110 */ V(1, 12, 3),
  /* 1111 */ V(1, 12, 3),

  /* 0000 0100 ... */
  /* 0000 */ V(12, 1, 3),	/* 132 */
  /* 0001 */ V(12, 1, 3),
  /* 0010 */ V(9, 8, 4),
  /* 0011 */ V(0, 12, 4),
  /* 0100 */ V(12, 0, 3),
  /* 0101 */ V(12, 0, 3),
  /* 0110 */ V(11, 4, 4),
  /* 0111 */ V(6, 10, 4),
  /* 1000 */ V(10, 6, 4),
  /* 1001 */ V(7, 9, 4),
  /* 1010 */ V(3, 11, 3),
  /* 1011 */ V(3, 11, 3),
  /* 1100 */ V(11, 3, 3),
  /* 1101 */ V(11, 3, 3),
  /* 1110 */ V(8, 8, 4),
  /* 1111 */ V(5, 10, 4),

  /* 0000 0101 ... */
  /* 0000 */ V(2, 11, 3),	/* 148 */
  /* 0001 */ V(2, 11, 3),
  /* 0010 */ V(10, 5, 4),
  /* 0011 */ V(6, 9, 4),
  /* 0100 */ V(10, 4, 3),
  /* 0101 */ V(10, 4, 3),
  /* 0110 */ V(7, 8, 4),
  /* 0111 */ V(8, 7, 4),
  /* 1000 */ V(9, 4, 3),
  /* 1001 */ V(9, 4, 3),
  /* 1010 */ V(7, 7, 4),
  /* 1011 */ V(7, 6, 4),
  /* 1100 */ V(11, 2, 2),
  /* 1101 */ V(11, 2, 2),
  /* 1110 */ V(11, 2, 2),
  /* 1111 */ V(11, 2, 2),

  /* 0000 0110 ... */
  /* 000  */ V(1, 11, 2),	/* 164 */
  /* 001  */ V(1, 11, 2),
  /* 010  */ V(11, 1, 2),
  /* 011  */ V(11, 1, 2),
  /* 100  */ V(0, 11, 3),
  /* 101  */ V(11, 0, 3),
  /* 110  */ V(9, 6, 3),
  /* 111  */ V(4, 10, 3),

  /* 0000 0111 ... */
  /* 000  */ V(3, 10, 3),	/* 172 */
  /* 001  */ V(10, 3, 3),
  /* 010  */ V(5, 9, 3),
  /* 011  */ V(9, 5, 3),
  /* 100  */ V(2, 10, 2),
  /* 101  */ V(2, 10, 2),
  /* 110  */ V(10, 2, 2),
  /* 111  */ V(10, 2, 2),

  /* 0000 1000 ... */
  /* 000  */ V(1, 10, 2),	/* 180 */
  /* 001  */ V(1, 10, 2),
  /* 010  */ V(10, 1, 2),
  /* 011  */ V(10, 1, 2),
  /* 100  */ V(0, 10, 3),
  /* 101  */ V(6, 8, 3),
  /* 110  */ V(10, 0, 2),
  /* 111  */ V(10, 0, 2),

  /* 0000 1001 ... */
  /* 000  */ V(8, 6, 3),	/* 188 */
  /* 001  */ V(4, 9, 3),
  /* 010  */ V(9, 3, 2),
  /* 011  */ V(9, 3, 2),
  /* 100  */ V(3, 9, 3),
  /* 101  */ V(5, 8, 3),
  /* 110  */ V(8, 5, 3),
  /* 111  */ V(6, 7, 3),

  /* 0000 1010 ... */
  /* 000  */ V(2, 9, 2),	/* 196 */
  /* 001  */ V(2, 9, 2),
  /* 010  */ V(9, 2, 2),
  /* 011  */ V(9, 2, 2),
  /* 100  */ V(5, 7, 3),
  /* 101  */ V(7, 5, 3),
  /* 110  */ V(3, 8, 2),
  /* 111  */ V(3, 8, 2),

  /* 0000 1011 ... */
  /* 000  */ V(8, 3, 2),	/* 204 */
  /* 001  */ V(8, 3, 2),
  /* 010  */ V(6, 6, 3),
  /* 011  */ V(4, 7, 3),
  /* 100  */ V(7, 4, 3),
  /* 101  */ V(5, 6, 3),
  /* 110  */ V(6, 5, 3),
  /* 111  */ V(7, 3, 3),

  /* 0000 1100 ... */
  /* 0    */ V(1, 9, 1),	/* 212 */
  /* 1    */ V(9, 1, 1),

  /* 0000 1101 ... */
  /* 00   */ V(0, 9, 2),	/* 214 */
  /* 01   */ V(9, 0, 2),
  /* 10   */ V(4, 8, 2),
  /* 11   */ V(8, 4, 2),

  /* 0000 1110 ... */
  /* 000  */ V(7, 2, 2),	/* 218 */
  /* 001  */ V(7, 2, 2),
  /* 010  */ V(4, 6, 3),
  /* 011  */ V(6, 4, 3),
  /* 100  */ V(2, 8, 1),
  /* 101  */ V(2, 8, 1),
  /* 110  */ V(2, 8, 1),
  /* 111  */ V(2, 8, 1),

  /* 0000 1111 ... */
  /* 0    */ V(8, 2, 1),	/* 226 */
  /* 1    */ V(1, 8, 1),

  /* 0001 0000 ... */
  /* 00   */ V(3, 7, 2),	/* 228 */
  /* 01   */ V(2, 7, 2),
  /* 10   */ V(1, 7, 1),
  /* 11   */ V(1, 7, 1),

  /* 0001 0001 ... */
  /* 00   */ V(7, 1, 1),	/* 232 */
  /* 01   */ V(7, 1, 1),
  /* 10   */ V(5, 5, 2),
  /* 11   */ V(0, 7, 2),

  /* 0001 0010 ... */
  /* 00   */ V(7, 0, 2),	/* 236 */
  /* 01   */ V(3, 6, 2),
  /* 10   */ V(6, 3, 2),
  /* 11   */ V(4, 5, 2),

  /* 0001 0011 ... */
  /* 00   */ V(5, 4, 2),	/* 240 */
  /* 01   */ V(2, 6, 2),
  /* 10   */ V(6, 2, 2),
  /* 11   */ V(3, 5, 2),

  /* 0001 0101 ... */
  /* 0    */ V(0, 8, 1),	/* 244 */
  /* 1    */ V(8, 0, 1),

  /* 0001 0110 ... */
  /* 0    */ V(1, 6, 1),	/* 246 */
  /* 1    */ V(6, 1, 1),

  /* 0001 0111 ... */
  /* 0    */ V(0, 6, 1),	/* 248 */
  /* 1    */ V(6, 0, 1),

  /* 0001 1000 ... */
  /* 00   */ V(5, 3, 2),	/* 250 */
  /* 01   */ V(4, 4, 2),
  /* 10   */ V(2, 5, 1),
  /* 11   */ V(2, 5, 1),

  /* 0001 1001 ... */
  /* 0    */ V(5, 2, 1),	/* 254 */
  /* 1    */ V(0, 5, 1),

  /* 0001 1100 ... */
  /* 0    */ V(3, 4, 1),	/* 256 */
  /* 1    */ V(4, 3, 1),

  /* 0001 1101 ... */
  /* 0    */ V(5, 0, 1),	/* 258 */
  /* 1    */ V(2, 4, 1),

  /* 0001 1110 ... */
  /* 0    */ V(4, 2, 1),	/* 260 */
  /* 1    */ V(3, 3, 1),

  /* 0000 0000 0000 ... */
  /* 0000 */ PTR(388, 3),	/* 262 */
  /* 0001 */ V(15, 15, 4),
  /* 0010 */ V(14, 15, 4),
  /* 0011 */ V(13, 15, 4),
  /* 0100 */ V(14, 14, 4),
  /* 0101 */ V(12, 15, 4),
  /* 0110 */ V(13, 14, 4),
  /* 0111 */ V(11, 15, 4),
  /* 1000 */ V(15, 11, 4),
  /* 1001 */ V(12, 14, 4),
  /* 1010 */ V(13, 12, 4),
  /* 1011 */ PTR(396, 1),
  /* 1100 */ V(14, 12, 3),
  /* 1101 */ V(14, 12, 3),
  /* 1110 */ V(13, 13, 3),
  /* 1111 */ V(13, 13, 3),

  /* 0000 0000 0001 ... */
  /* 0000 */ V(15, 10, 4),	/* 278 */
  /* 0001 */ V(12, 13, 4),
  /* 0010 */ V(11, 14, 3),
  /* 0011 */ V(11, 14, 3),
  /* 0100 */ V(14, 11, 3),
  /* 0101 */ V(14, 11, 3),
  /* 0110 */ V(9, 15, 3),
  /* 0111 */ V(9, 15, 3),
  /* 1000 */ V(15, 9, 3),
  /* 1001 */ V(15, 9, 3),
  /* 1010 */ V(14, 10, 3),
  /* 1011 */ V(14, 10, 3),
  /* 1100 */ V(11, 13, 3),
  /* 1101 */ V(11, 13, 3),
  /* 1110 */ V(13, 11, 3),
  /* 1111 */ V(13, 11, 3),

  /* 0000 0000 0010 ... */
  /* 0000 */ V(8, 15, 3),	/* 294 */
  /* 0001 */ V(8, 15, 3),
  /* 0010 */ V(15, 8, 3),
  /* 0011 */ V(15, 8, 3),
  /* 0100 */ V(12, 12, 3),
  /* 0101 */ V(12, 12, 3),
  /* 0110 */ V(10, 14, 4),
  /* 0111 */ V(9, 14, 4),
  /* 1000 */ V(8, 14, 3),
  /* 1001 */ V(8, 14, 3),
  /* 1010 */ V(7, 15, 4),
  /* 1011 */ V(7, 14, 4),
  /* 1100 */ V(15, 7, 2),
  /* 1101 */ V(15, 7, 2),
  /* 1110 */ V(15, 7, 2),
  /* 1111 */ V(15, 7, 2),

  /* 0000 0000 0011 ... */
  /* 000  */ V(13, 10, 2),	/* 310 */
  /* 001  */ V(13, 10, 2),
  /* 010  */ V(10, 13, 3),
  /* 011  */ V(11, 12, 3),
  /* 100  */ V(12, 11, 3),
  /* 101  */ V(15, 6, 3),
  /* 110  */ V(6, 15, 2),
  /* 111  */ V(6, 15, 2),

  /* 0000 0000 0100 ... */
  /* 00   */ V(14, 8, 2),	/* 318 */
  /* 01   */ V(5, 15, 2),
  /* 10   */ V(9, 13, 2),
  /* 11   */ V(13, 9, 2),

  /* 0000 0000 0101 ... */
  /* 00   */ V(15, 5, 2),	/* 322 */
  /* 01   */ V(14, 7, 2),
  /* 10   */ V(10, 12, 2),
  /* 11   */ V(11, 11, 2),

  /* 0000 0000 0110 ... */
  /* 000  */ V(4, 15, 2),	/* 326 */
  /* 001  */ V(4, 15, 2),
  /* 010  */ V(15, 4, 2),
  /* 011  */ V(15, 4, 2),
  /* 100  */ V(12, 10, 3),
  /* 101  */ V(14, 6, 3),
  /* 110  */ V(15, 3, 2),
  /* 111  */ V(15, 3, 2),

  /* 0000 0000 0111 ... */
  /* 00   */ V(3, 15, 1),	/* 334 */
  /* 01   */ V(3, 15, 1),
  /* 10   */ V(8, 13, 2),
  /* 11   */ V(13, 8, 2),

  /* 0000 0000 1000 ... */
  /* 0    */ V(2, 15, 1),	/* 338 */
  /* 1    */ V(15, 2, 1),

  /* 0000 0000 1001 ... */
  /* 00   */ V(6, 14, 2),	/* 340 */
  /* 01   */ V(9, 12, 2),
  /* 10   */ V(0, 15, 1),
  /* 11   */ V(0, 15, 1),

  /* 0000 0000 1010 ... */
  /* 00   */ V(12, 9, 2),	/* 344 */
  /* 01   */ V(5, 14, 2),
  /* 10   */ V(10, 11, 1),
  /* 11   */ V(10, 11, 1),

  /* 0000 0000 1011 ... */
  /* 00   */ V(7, 13, 2),	/* 348 */
  /* 01   */ V(13, 7, 2),
  /* 10   */ V(4, 14, 1),
  /* 11   */ V(4, 14, 1),

  /* 0000 0000 1100 ... */
  /* 00   */ V(12, 8, 2),	/* 352 */
  /* 01   */ V(13, 6, 2),
  /* 10   */ V(3, 14, 1),
  /* 11   */ V(3, 14, 1),

  /* 0000 0000 1101 ... */
  /* 00   */ V(11, 9, 1),	/* 356 */
  /* 01   */ V(11, 9, 1),
  /* 10   */ V(9, 11, 2),
  /* 11   */ V(10, 10, 2),

  /* 0000 0001 0001 ... */
  /* 0    */ V(11, 10, 1),	/* 360 */
  /* 1    */ V(14, 5, 1),

  /* 0000 0001 0010 ... */
  /* 0    */ V(14, 4, 1),	/* 362 */
  /* 1    */ V(8, 12, 1),

  /* 0000 0001 0011 ... */
  /* 0    */ V(6, 13, 1),	/* 364 */
  /* 1    */ V(14, 3, 1),

  /* 0000 0001 0101 ... */
  /* 0    */ V(2, 14, 1),	/* 366 */
  /* 1    */ V(0, 14, 1),

  /* 0000 0001 1000 ... */
  /* 0    */ V(14, 0, 1),	/* 368 */
  /* 1    */ V(5, 13, 1),

  /* 0000 0001 1001 ... */
  /* 0    */ V(13, 5, 1),	/* 370 */
  /* 1    */ V(7, 12, 1),

  /* 0000 0001 1010 ... */
  /* 0    */ V(12, 7, 1),	/* 372 */
  /* 1    */ V(4, 13, 1),

  /* 0000 0001 1011 ... */
  /* 0    */ V(8, 11, 1),	/* 374 */
  /* 1    */ V(11, 8, 1),

  /* 0000 0001 1100 ... */
  /* 0    */ V(13, 4, 1),	/* 376 */
  /* 1    */ V(9, 10, 1),

  /* 0000 0001 1101 ... */
  /* 0    */ V(10, 9, 1),	/* 378 */
  /* 1    */ V(6, 12, 1),

  /* 0000 0010 0000 ... */
  /* 0    */ V(13, 3, 1),	/* 380 */
  /* 1    */ V(7, 11, 1),

  /* 0000 0010 0101 ... */
  /* 0    */ V(5, 12, 1),	/* 382 */
  /* 1    */ V(12, 5, 1),

  /* 0000 0010 0110 ... */
  /* 0    */ V(9, 9, 1),	/* 384 */
  /* 1    */ V(7, 10, 1),

  /* 0000 0010 1000 ... */
  /* 0    */ V(10, 7, 1),	/* 386 */
  /* 1    */ V(9, 7, 1),

  /* 0000 0000 0000 0000 ... */
  /* 000  */ V(15, 14, 3),	/* 388 */
  /* 001  */ V(15, 12, 3),
  /* 010  */ V(15, 13, 2),
  /* 011  */ V(15, 13, 2),
  /* 100  */ V(14, 13, 1),
  /* 101  */ V(14, 13, 1),
  /* 110  */ V(14, 13, 1),
  /* 111  */ V(14, 13, 1),

  /* 0000 0000 0000 1011 ... */
  /* 0    */ V(10, 15, 1),	/* 396 */
  /* 1    */ V(14, 9, 1)
];

const hufftab15 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 4),
  /* 0011 */ PTR(64, 4),
  /* 0100 */ PTR(80, 4),
  /* 0101 */ PTR(96, 3),
  /* 0110 */ PTR(104, 3),
  /* 0111 */ PTR(112, 2),
  /* 1000 */ PTR(116, 1),
  /* 1001 */ PTR(118, 1),
  /* 1010 */ V(1, 1, 3),
  /* 1011 */ V(1, 1, 3),
  /* 1100 */ V(0, 1, 4),
  /* 1101 */ V(1, 0, 4),
  /* 1110 */ V(0, 0, 3),
  /* 1111 */ V(0, 0, 3),

  /* 0000 ... */
  /* 0000 */ PTR(120, 4),	/* 16 */
  /* 0001 */ PTR(136, 4),
  /* 0010 */ PTR(152, 4),
  /* 0011 */ PTR(168, 4),
  /* 0100 */ PTR(184, 4),
  /* 0101 */ PTR(200, 3),
  /* 0110 */ PTR(208, 3),
  /* 0111 */ PTR(216, 4),
  /* 1000 */ PTR(232, 3),
  /* 1001 */ PTR(240, 3),
  /* 1010 */ PTR(248, 3),
  /* 1011 */ PTR(256, 3),
  /* 1100 */ PTR(264, 2),
  /* 1101 */ PTR(268, 3),
  /* 1110 */ PTR(276, 3),
  /* 1111 */ PTR(284, 2),

  /* 0001 ... */
  /* 0000 */ PTR(288, 2),	/* 32 */
  /* 0001 */ PTR(292, 2),
  /* 0010 */ PTR(296, 2),
  /* 0011 */ PTR(300, 2),
  /* 0100 */ PTR(304, 2),
  /* 0101 */ PTR(308, 2),
  /* 0110 */ PTR(312, 2),
  /* 0111 */ PTR(316, 2),
  /* 1000 */ PTR(320, 1),
  /* 1001 */ PTR(322, 1),
  /* 1010 */ PTR(324, 1),
  /* 1011 */ PTR(326, 2),
  /* 1100 */ PTR(330, 1),
  /* 1101 */ PTR(332, 1),
  /* 1110 */ PTR(334, 2),
  /* 1111 */ PTR(338, 1),

  /* 0010 ... */
  /* 0000 */ PTR(340, 1),	/* 48 */
  /* 0001 */ PTR(342, 1),
  /* 0010 */ V(9, 1, 4),
  /* 0011 */ PTR(344, 1),
  /* 0100 */ PTR(346, 1),
  /* 0101 */ PTR(348, 1),
  /* 0110 */ PTR(350, 1),
  /* 0111 */ PTR(352, 1),
  /* 1000 */ V(2, 8, 4),
  /* 1001 */ V(8, 2, 4),
  /* 1010 */ V(1, 8, 4),
  /* 1011 */ V(8, 1, 4),
  /* 1100 */ PTR(354, 1),
  /* 1101 */ PTR(356, 1),
  /* 1110 */ PTR(358, 1),
  /* 1111 */ PTR(360, 1),

  /* 0011 ... */
  /* 0000 */ V(2, 7, 4),	/* 64 */
  /* 0001 */ V(7, 2, 4),
  /* 0010 */ V(6, 4, 4),
  /* 0011 */ V(1, 7, 4),
  /* 0100 */ V(5, 5, 4),
  /* 0101 */ V(7, 1, 4),
  /* 0110 */ PTR(362, 1),
  /* 0111 */ V(3, 6, 4),
  /* 1000 */ V(6, 3, 4),
  /* 1001 */ V(4, 5, 4),
  /* 1010 */ V(5, 4, 4),
  /* 1011 */ V(2, 6, 4),
  /* 1100 */ V(6, 2, 4),
  /* 1101 */ V(1, 6, 4),
  /* 1110 */ PTR(364, 1),
  /* 1111 */ V(3, 5, 4),

  /* 0100 ... */
  /* 0000 */ V(6, 1, 3),	/* 80 */
  /* 0001 */ V(6, 1, 3),
  /* 0010 */ V(5, 3, 4),
  /* 0011 */ V(4, 4, 4),
  /* 0100 */ V(2, 5, 3),
  /* 0101 */ V(2, 5, 3),
  /* 0110 */ V(5, 2, 3),
  /* 0111 */ V(5, 2, 3),
  /* 1000 */ V(1, 5, 3),
  /* 1001 */ V(1, 5, 3),
  /* 1010 */ V(5, 1, 3),
  /* 1011 */ V(5, 1, 3),
  /* 1100 */ V(0, 5, 4),
  /* 1101 */ V(5, 0, 4),
  /* 1110 */ V(3, 4, 3),
  /* 1111 */ V(3, 4, 3),

  /* 0101 ... */
  /* 000  */ V(4, 3, 3),	/* 96 */
  /* 001  */ V(2, 4, 3),
  /* 010  */ V(4, 2, 3),
  /* 011  */ V(3, 3, 3),
  /* 100  */ V(4, 1, 2),
  /* 101  */ V(4, 1, 2),
  /* 110  */ V(1, 4, 3),
  /* 111  */ V(0, 4, 3),

  /* 0110 ... */
  /* 000  */ V(2, 3, 2),	/* 104 */
  /* 001  */ V(2, 3, 2),
  /* 010  */ V(3, 2, 2),
  /* 011  */ V(3, 2, 2),
  /* 100  */ V(4, 0, 3),
  /* 101  */ V(0, 3, 3),
  /* 110  */ V(1, 3, 2),
  /* 111  */ V(1, 3, 2),

  /* 0111 ... */
  /* 00   */ V(3, 1, 2),	/* 112 */
  /* 01   */ V(3, 0, 2),
  /* 10   */ V(2, 2, 1),
  /* 11   */ V(2, 2, 1),

  /* 1000 ... */
  /* 0    */ V(1, 2, 1),	/* 116 */
  /* 1    */ V(2, 1, 1),

  /* 1001 ... */
  /* 0    */ V(0, 2, 1),	/* 118 */
  /* 1    */ V(2, 0, 1),

  /* 0000 0000 ... */
  /* 0000 */ PTR(366, 1),	/* 120 */
  /* 0001 */ PTR(368, 1),
  /* 0010 */ V(14, 14, 4),
  /* 0011 */ PTR(370, 1),
  /* 0100 */ PTR(372, 1),
  /* 0101 */ PTR(374, 1),
  /* 0110 */ V(15, 11, 4),
  /* 0111 */ PTR(376, 1),
  /* 1000 */ V(13, 13, 4),
  /* 1001 */ V(10, 15, 4),
  /* 1010 */ V(15, 10, 4),
  /* 1011 */ V(11, 14, 4),
  /* 1100 */ V(14, 11, 4),
  /* 1101 */ V(12, 13, 4),
  /* 1110 */ V(13, 12, 4),
  /* 1111 */ V(9, 15, 4),

  /* 0000 0001 ... */
  /* 0000 */ V(15, 9, 4),	/* 136 */
  /* 0001 */ V(14, 10, 4),
  /* 0010 */ V(11, 13, 4),
  /* 0011 */ V(13, 11, 4),
  /* 0100 */ V(8, 15, 4),
  /* 0101 */ V(15, 8, 4),
  /* 0110 */ V(12, 12, 4),
  /* 0111 */ V(9, 14, 4),
  /* 1000 */ V(14, 9, 4),
  /* 1001 */ V(7, 15, 4),
  /* 1010 */ V(15, 7, 4),
  /* 1011 */ V(10, 13, 4),
  /* 1100 */ V(13, 10, 4),
  /* 1101 */ V(11, 12, 4),
  /* 1110 */ V(6, 15, 4),
  /* 1111 */ PTR(378, 1),

  /* 0000 0010 ... */
  /* 0000 */ V(12, 11, 3),	/* 152 */
  /* 0001 */ V(12, 11, 3),
  /* 0010 */ V(15, 6, 3),
  /* 0011 */ V(15, 6, 3),
  /* 0100 */ V(8, 14, 4),
  /* 0101 */ V(14, 8, 4),
  /* 0110 */ V(5, 15, 4),
  /* 0111 */ V(9, 13, 4),
  /* 1000 */ V(15, 5, 3),
  /* 1001 */ V(15, 5, 3),
  /* 1010 */ V(7, 14, 3),
  /* 1011 */ V(7, 14, 3),
  /* 1100 */ V(14, 7, 3),
  /* 1101 */ V(14, 7, 3),
  /* 1110 */ V(10, 12, 3),
  /* 1111 */ V(10, 12, 3),

  /* 0000 0011 ... */
  /* 0000 */ V(12, 10, 3),	/* 168 */
  /* 0001 */ V(12, 10, 3),
  /* 0010 */ V(11, 11, 3),
  /* 0011 */ V(11, 11, 3),
  /* 0100 */ V(13, 9, 4),
  /* 0101 */ V(8, 13, 4),
  /* 0110 */ V(4, 15, 3),
  /* 0111 */ V(4, 15, 3),
  /* 1000 */ V(15, 4, 3),
  /* 1001 */ V(15, 4, 3),
  /* 1010 */ V(3, 15, 3),
  /* 1011 */ V(3, 15, 3),
  /* 1100 */ V(15, 3, 3),
  /* 1101 */ V(15, 3, 3),
  /* 1110 */ V(13, 8, 3),
  /* 1111 */ V(13, 8, 3),

  /* 0000 0100 ... */
  /* 0000 */ V(14, 6, 3),	/* 184 */
  /* 0001 */ V(14, 6, 3),
  /* 0010 */ V(2, 15, 3),
  /* 0011 */ V(2, 15, 3),
  /* 0100 */ V(15, 2, 3),
  /* 0101 */ V(15, 2, 3),
  /* 0110 */ V(6, 14, 4),
  /* 0111 */ V(15, 0, 4),
  /* 1000 */ V(1, 15, 3),
  /* 1001 */ V(1, 15, 3),
  /* 1010 */ V(15, 1, 3),
  /* 1011 */ V(15, 1, 3),
  /* 1100 */ V(9, 12, 3),
  /* 1101 */ V(9, 12, 3),
  /* 1110 */ V(12, 9, 3),
  /* 1111 */ V(12, 9, 3),

  /* 0000 0101 ... */
  /* 000  */ V(5, 14, 3),	/* 200 */
  /* 001  */ V(10, 11, 3),
  /* 010  */ V(11, 10, 3),
  /* 011  */ V(14, 5, 3),
  /* 100  */ V(7, 13, 3),
  /* 101  */ V(13, 7, 3),
  /* 110  */ V(4, 14, 3),
  /* 111  */ V(14, 4, 3),

  /* 0000 0110 ... */
  /* 000  */ V(8, 12, 3),	/* 208 */
  /* 001  */ V(12, 8, 3),
  /* 010  */ V(3, 14, 3),
  /* 011  */ V(6, 13, 3),
  /* 100  */ V(13, 6, 3),
  /* 101  */ V(14, 3, 3),
  /* 110  */ V(9, 11, 3),
  /* 111  */ V(11, 9, 3),

  /* 0000 0111 ... */
  /* 0000 */ V(2, 14, 3),	/* 216 */
  /* 0001 */ V(2, 14, 3),
  /* 0010 */ V(10, 10, 3),
  /* 0011 */ V(10, 10, 3),
  /* 0100 */ V(14, 2, 3),
  /* 0101 */ V(14, 2, 3),
  /* 0110 */ V(1, 14, 3),
  /* 0111 */ V(1, 14, 3),
  /* 1000 */ V(14, 1, 3),
  /* 1001 */ V(14, 1, 3),
  /* 1010 */ V(0, 14, 4),
  /* 1011 */ V(14, 0, 4),
  /* 1100 */ V(5, 13, 3),
  /* 1101 */ V(5, 13, 3),
  /* 1110 */ V(13, 5, 3),
  /* 1111 */ V(13, 5, 3),

  /* 0000 1000 ... */
  /* 000  */ V(7, 12, 3),	/* 232 */
  /* 001  */ V(12, 7, 3),
  /* 010  */ V(4, 13, 3),
  /* 011  */ V(8, 11, 3),
  /* 100  */ V(13, 4, 2),
  /* 101  */ V(13, 4, 2),
  /* 110  */ V(11, 8, 3),
  /* 111  */ V(9, 10, 3),

  /* 0000 1001 ... */
  /* 000  */ V(10, 9, 3),	/* 240 */
  /* 001  */ V(6, 12, 3),
  /* 010  */ V(12, 6, 3),
  /* 011  */ V(3, 13, 3),
  /* 100  */ V(13, 3, 2),
  /* 101  */ V(13, 3, 2),
  /* 110  */ V(13, 2, 2),
  /* 111  */ V(13, 2, 2),

  /* 0000 1010 ... */
  /* 000  */ V(2, 13, 3),	/* 248 */
  /* 001  */ V(0, 13, 3),
  /* 010  */ V(1, 13, 2),
  /* 011  */ V(1, 13, 2),
  /* 100  */ V(7, 11, 2),
  /* 101  */ V(7, 11, 2),
  /* 110  */ V(11, 7, 2),
  /* 111  */ V(11, 7, 2),

  /* 0000 1011 ... */
  /* 000  */ V(13, 1, 2),	/* 256 */
  /* 001  */ V(13, 1, 2),
  /* 010  */ V(5, 12, 3),
  /* 011  */ V(13, 0, 3),
  /* 100  */ V(12, 5, 2),
  /* 101  */ V(12, 5, 2),
  /* 110  */ V(8, 10, 2),
  /* 111  */ V(8, 10, 2),

  /* 0000 1100 ... */
  /* 00   */ V(10, 8, 2),	/* 264 */
  /* 01   */ V(4, 12, 2),
  /* 10   */ V(12, 4, 2),
  /* 11   */ V(6, 11, 2),

  /* 0000 1101 ... */
  /* 000  */ V(11, 6, 2),	/* 268 */
  /* 001  */ V(11, 6, 2),
  /* 010  */ V(9, 9, 3),
  /* 011  */ V(0, 12, 3),
  /* 100  */ V(3, 12, 2),
  /* 101  */ V(3, 12, 2),
  /* 110  */ V(12, 3, 2),
  /* 111  */ V(12, 3, 2),

  /* 0000 1110 ... */
  /* 000  */ V(7, 10, 2),	/* 276 */
  /* 001  */ V(7, 10, 2),
  /* 010  */ V(10, 7, 2),
  /* 011  */ V(10, 7, 2),
  /* 100  */ V(10, 6, 2),
  /* 101  */ V(10, 6, 2),
  /* 110  */ V(12, 0, 3),
  /* 111  */ V(0, 11, 3),

  /* 0000 1111 ... */
  /* 00   */ V(12, 2, 1),	/* 284 */
  /* 01   */ V(12, 2, 1),
  /* 10   */ V(2, 12, 2),
  /* 11   */ V(5, 11, 2),

  /* 0001 0000 ... */
  /* 00   */ V(11, 5, 2),	/* 288 */
  /* 01   */ V(1, 12, 2),
  /* 10   */ V(8, 9, 2),
  /* 11   */ V(9, 8, 2),

  /* 0001 0001 ... */
  /* 00   */ V(12, 1, 2),	/* 292 */
  /* 01   */ V(4, 11, 2),
  /* 10   */ V(11, 4, 2),
  /* 11   */ V(6, 10, 2),

  /* 0001 0010 ... */
  /* 00   */ V(3, 11, 2),	/* 296 */
  /* 01   */ V(7, 9, 2),
  /* 10   */ V(11, 3, 1),
  /* 11   */ V(11, 3, 1),

  /* 0001 0011 ... */
  /* 00   */ V(9, 7, 2),	/* 300 */
  /* 01   */ V(8, 8, 2),
  /* 10   */ V(2, 11, 2),
  /* 11   */ V(5, 10, 2),

  /* 0001 0100 ... */
  /* 00   */ V(11, 2, 1),	/* 304 */
  /* 01   */ V(11, 2, 1),
  /* 10   */ V(10, 5, 2),
  /* 11   */ V(1, 11, 2),

  /* 0001 0101 ... */
  /* 00   */ V(11, 1, 1),	/* 308 */
  /* 01   */ V(11, 1, 1),
  /* 10   */ V(11, 0, 2),
  /* 11   */ V(6, 9, 2),

  /* 0001 0110 ... */
  /* 00   */ V(9, 6, 2),	/* 312 */
  /* 01   */ V(4, 10, 2),
  /* 10   */ V(10, 4, 2),
  /* 11   */ V(7, 8, 2),

  /* 0001 0111 ... */
  /* 00   */ V(8, 7, 2),	/* 316 */
  /* 01   */ V(3, 10, 2),
  /* 10   */ V(10, 3, 1),
  /* 11   */ V(10, 3, 1),

  /* 0001 1000 ... */
  /* 0    */ V(5, 9, 1),	/* 320 */
  /* 1    */ V(9, 5, 1),

  /* 0001 1001 ... */
  /* 0    */ V(2, 10, 1),	/* 322 */
  /* 1    */ V(10, 2, 1),

  /* 0001 1010 ... */
  /* 0    */ V(1, 10, 1),	/* 324 */
  /* 1    */ V(10, 1, 1),

  /* 0001 1011 ... */
  /* 00   */ V(0, 10, 2),	/* 326 */
  /* 01   */ V(10, 0, 2),
  /* 10   */ V(6, 8, 1),
  /* 11   */ V(6, 8, 1),

  /* 0001 1100 ... */
  /* 0    */ V(8, 6, 1),	/* 330 */
  /* 1    */ V(4, 9, 1),

  /* 0001 1101 ... */
  /* 0    */ V(9, 4, 1),	/* 332 */
  /* 1    */ V(3, 9, 1),

  /* 0001 1110 ... */
  /* 00   */ V(9, 3, 1),	/* 334 */
  /* 01   */ V(9, 3, 1),
  /* 10   */ V(7, 7, 2),
  /* 11   */ V(0, 9, 2),

  /* 0001 1111 ... */
  /* 0    */ V(5, 8, 1),	/* 338 */
  /* 1    */ V(8, 5, 1),

  /* 0010 0000 ... */
  /* 0    */ V(2, 9, 1),	/* 340 */
  /* 1    */ V(6, 7, 1),

  /* 0010 0001 ... */
  /* 0    */ V(7, 6, 1),	/* 342 */
  /* 1    */ V(9, 2, 1),

  /* 0010 0011 ... */
  /* 0    */ V(1, 9, 1),	/* 344 */
  /* 1    */ V(9, 0, 1),

  /* 0010 0100 ... */
  /* 0    */ V(4, 8, 1),	/* 346 */
  /* 1    */ V(8, 4, 1),

  /* 0010 0101 ... */
  /* 0    */ V(5, 7, 1),	/* 348 */
  /* 1    */ V(7, 5, 1),

  /* 0010 0110 ... */
  /* 0    */ V(3, 8, 1),	/* 350 */
  /* 1    */ V(8, 3, 1),

  /* 0010 0111 ... */
  /* 0    */ V(6, 6, 1),	/* 352 */
  /* 1    */ V(4, 7, 1),

  /* 0010 1100 ... */
  /* 0    */ V(7, 4, 1),	/* 354 */
  /* 1    */ V(0, 8, 1),

  /* 0010 1101 ... */
  /* 0    */ V(8, 0, 1),	/* 356 */
  /* 1    */ V(5, 6, 1),

  /* 0010 1110 ... */
  /* 0    */ V(6, 5, 1),	/* 358 */
  /* 1    */ V(3, 7, 1),

  /* 0010 1111 ... */
  /* 0    */ V(7, 3, 1),	/* 360 */
  /* 1    */ V(4, 6, 1),

  /* 0011 0110 ... */
  /* 0    */ V(0, 7, 1),	/* 362 */
  /* 1    */ V(7, 0, 1),

  /* 0011 1110 ... */
  /* 0    */ V(0, 6, 1),	/* 364 */
  /* 1    */ V(6, 0, 1),

  /* 0000 0000 0000 ... */
  /* 0    */ V(15, 15, 1),	/* 366 */
  /* 1    */ V(14, 15, 1),

  /* 0000 0000 0001 ... */
  /* 0    */ V(15, 14, 1),	/* 368 */
  /* 1    */ V(13, 15, 1),

  /* 0000 0000 0011 ... */
  /* 0    */ V(15, 13, 1),	/* 370 */
  /* 1    */ V(12, 15, 1),

  /* 0000 0000 0100 ... */
  /* 0    */ V(15, 12, 1),	/* 372 */
  /* 1    */ V(13, 14, 1),

  /* 0000 0000 0101 ... */
  /* 0    */ V(14, 13, 1),	/* 374 */
  /* 1    */ V(11, 15, 1),

  /* 0000 0000 0111 ... */
  /* 0    */ V(12, 14, 1),	/* 376 */
  /* 1    */ V(14, 12, 1),

  /* 0000 0001 1111 ... */
  /* 0    */ V(10, 14, 1),	/* 378 */
  /* 1    */ V(0, 15, 1)
];

const hufftab16 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 4),
  /* 0011 */ PTR(64, 2),
  /* 0100 */ V(1, 1, 4),
  /* 0101 */ V(0, 1, 4),
  /* 0110 */ V(1, 0, 3),
  /* 0111 */ V(1, 0, 3),
  /* 1000 */ V(0, 0, 1),
  /* 1001 */ V(0, 0, 1),
  /* 1010 */ V(0, 0, 1),
  /* 1011 */ V(0, 0, 1),
  /* 1100 */ V(0, 0, 1),
  /* 1101 */ V(0, 0, 1),
  /* 1110 */ V(0, 0, 1),
  /* 1111 */ V(0, 0, 1),

  /* 0000 ... */
  /* 0000 */ PTR(68, 3),	/* 16 */
  /* 0001 */ PTR(76, 3),
  /* 0010 */ PTR(84, 2),
  /* 0011 */ V(15, 15, 4),
  /* 0100 */ PTR(88, 2),
  /* 0101 */ PTR(92, 1),
  /* 0110 */ PTR(94, 4),
  /* 0111 */ V(15, 2, 4),
  /* 1000 */ PTR(110, 1),
  /* 1001 */ V(1, 15, 4),
  /* 1010 */ V(15, 1, 4),
  /* 1011 */ PTR(112, 4),
  /* 1100 */ PTR(128, 4),
  /* 1101 */ PTR(144, 4),
  /* 1110 */ PTR(160, 4),
  /* 1111 */ PTR(176, 4),

  /* 0001 ... */
  /* 0000 */ PTR(192, 4),	/* 32 */
  /* 0001 */ PTR(208, 3),
  /* 0010 */ PTR(216, 3),
  /* 0011 */ PTR(224, 3),
  /* 0100 */ PTR(232, 3),
  /* 0101 */ PTR(240, 3),
  /* 0110 */ PTR(248, 3),
  /* 0111 */ PTR(256, 3),
  /* 1000 */ PTR(264, 2),
  /* 1001 */ PTR(268, 2),
  /* 1010 */ PTR(272, 1),
  /* 1011 */ PTR(274, 2),
  /* 1100 */ PTR(278, 2),
  /* 1101 */ PTR(282, 1),
  /* 1110 */ V(5, 1, 4),
  /* 1111 */ PTR(284, 1),

  /* 0010 ... */
  /* 0000 */ PTR(286, 1),	/* 48 */
  /* 0001 */ PTR(288, 1),
  /* 0010 */ PTR(290, 1),
  /* 0011 */ V(1, 4, 4),
  /* 0100 */ V(4, 1, 4),
  /* 0101 */ PTR(292, 1),
  /* 0110 */ V(2, 3, 4),
  /* 0111 */ V(3, 2, 4),
  /* 1000 */ V(1, 3, 3),
  /* 1001 */ V(1, 3, 3),
  /* 1010 */ V(3, 1, 3),
  /* 1011 */ V(3, 1, 3),
  /* 1100 */ V(0, 3, 4),
  /* 1101 */ V(3, 0, 4),
  /* 1110 */ V(2, 2, 3),
  /* 1111 */ V(2, 2, 3),

  /* 0011 ... */
  /* 00   */ V(1, 2, 2),	/* 64 */
  /* 01   */ V(2, 1, 2),
  /* 10   */ V(0, 2, 2),
  /* 11   */ V(2, 0, 2),

  /* 0000 0000 ... */
  /* 000  */ V(14, 15, 3),	/* 68 */
  /* 001  */ V(15, 14, 3),
  /* 010  */ V(13, 15, 3),
  /* 011  */ V(15, 13, 3),
  /* 100  */ V(12, 15, 3),
  /* 101  */ V(15, 12, 3),
  /* 110  */ V(11, 15, 3),
  /* 111  */ V(15, 11, 3),

  /* 0000 0001 ... */
  /* 000  */ V(10, 15, 2),	/* 76 */
  /* 001  */ V(10, 15, 2),
  /* 010  */ V(15, 10, 3),
  /* 011  */ V(9, 15, 3),
  /* 100  */ V(15, 9, 3),
  /* 101  */ V(15, 8, 3),
  /* 110  */ V(8, 15, 2),
  /* 111  */ V(8, 15, 2),

  /* 0000 0010 ... */
  /* 00   */ V(7, 15, 2),	/* 84 */
  /* 01   */ V(15, 7, 2),
  /* 10   */ V(6, 15, 2),
  /* 11   */ V(15, 6, 2),

  /* 0000 0100 ... */
  /* 00   */ V(5, 15, 2),	/* 88 */
  /* 01   */ V(15, 5, 2),
  /* 10   */ V(4, 15, 1),
  /* 11   */ V(4, 15, 1),

  /* 0000 0101 ... */
  /* 0    */ V(15, 4, 1),	/* 92 */
  /* 1    */ V(15, 3, 1),

  /* 0000 0110 ... */
  /* 0000 */ V(15, 0, 1),	/* 94 */
  /* 0001 */ V(15, 0, 1),
  /* 0010 */ V(15, 0, 1),
  /* 0011 */ V(15, 0, 1),
  /* 0100 */ V(15, 0, 1),
  /* 0101 */ V(15, 0, 1),
  /* 0110 */ V(15, 0, 1),
  /* 0111 */ V(15, 0, 1),
  /* 1000 */ V(3, 15, 2),
  /* 1001 */ V(3, 15, 2),
  /* 1010 */ V(3, 15, 2),
  /* 1011 */ V(3, 15, 2),
  /* 1100 */ PTR(294, 4),
  /* 1101 */ PTR(310, 3),
  /* 1110 */ PTR(318, 3),
  /* 1111 */ PTR(326, 3),

  /* 0000 1000 ... */
  /* 0    */ V(2, 15, 1),	/* 110 */
  /* 1    */ V(0, 15, 1),

  /* 0000 1011 ... */
  /* 0000 */ PTR(334, 2),	/* 112 */
  /* 0001 */ PTR(338, 2),
  /* 0010 */ PTR(342, 2),
  /* 0011 */ PTR(346, 1),
  /* 0100 */ PTR(348, 2),
  /* 0101 */ PTR(352, 2),
  /* 0110 */ PTR(356, 1),
  /* 0111 */ PTR(358, 2),
  /* 1000 */ PTR(362, 2),
  /* 1001 */ PTR(366, 2),
  /* 1010 */ PTR(370, 2),
  /* 1011 */ V(14, 3, 4),
  /* 1100 */ PTR(374, 1),
  /* 1101 */ PTR(376, 1),
  /* 1110 */ PTR(378, 1),
  /* 1111 */ PTR(380, 1),

  /* 0000 1100 ... */
  /* 0000 */ PTR(382, 1),	/* 128 */
  /* 0001 */ PTR(384, 1),
  /* 0010 */ PTR(386, 1),
  /* 0011 */ V(0, 13, 4),
  /* 0100 */ PTR(388, 1),
  /* 0101 */ PTR(390, 1),
  /* 0110 */ PTR(392, 1),
  /* 0111 */ V(3, 12, 4),
  /* 1000 */ PTR(394, 1),
  /* 1001 */ V(1, 12, 4),
  /* 1010 */ V(12, 0, 4),
  /* 1011 */ PTR(396, 1),
  /* 1100 */ V(14, 2, 3),
  /* 1101 */ V(14, 2, 3),
  /* 1110 */ V(2, 14, 4),
  /* 1111 */ V(1, 14, 4),

  /* 0000 1101 ... */
  /* 0000 */ V(13, 3, 4),	/* 144 */
  /* 0001 */ V(2, 13, 4),
  /* 0010 */ V(13, 2, 4),
  /* 0011 */ V(13, 1, 4),
  /* 0100 */ V(3, 11, 4),
  /* 0101 */ PTR(398, 1),
  /* 0110 */ V(1, 13, 3),
  /* 0111 */ V(1, 13, 3),
  /* 1000 */ V(12, 4, 4),
  /* 1001 */ V(6, 11, 4),
  /* 1010 */ V(12, 3, 4),
  /* 1011 */ V(10, 7, 4),
  /* 1100 */ V(2, 12, 3),
  /* 1101 */ V(2, 12, 3),
  /* 1110 */ V(12, 2, 4),
  /* 1111 */ V(11, 5, 4),

  /* 0000 1110 ... */
  /* 0000 */ V(12, 1, 4),	/* 160 */
  /* 0001 */ V(0, 12, 4),
  /* 0010 */ V(4, 11, 4),
  /* 0011 */ V(11, 4, 4),
  /* 0100 */ V(6, 10, 4),
  /* 0101 */ V(10, 6, 4),
  /* 0110 */ V(11, 3, 3),
  /* 0111 */ V(11, 3, 3),
  /* 1000 */ V(5, 10, 4),
  /* 1001 */ V(10, 5, 4),
  /* 1010 */ V(2, 11, 3),
  /* 1011 */ V(2, 11, 3),
  /* 1100 */ V(11, 2, 3),
  /* 1101 */ V(11, 2, 3),
  /* 1110 */ V(1, 11, 3),
  /* 1111 */ V(1, 11, 3),

  /* 0000 1111 ... */
  /* 0000 */ V(11, 1, 3),	/* 176 */
  /* 0001 */ V(11, 1, 3),
  /* 0010 */ V(0, 11, 4),
  /* 0011 */ V(11, 0, 4),
  /* 0100 */ V(6, 9, 4),
  /* 0101 */ V(9, 6, 4),
  /* 0110 */ V(4, 10, 4),
  /* 0111 */ V(10, 4, 4),
  /* 1000 */ V(7, 8, 4),
  /* 1001 */ V(8, 7, 4),
  /* 1010 */ V(10, 3, 3),
  /* 1011 */ V(10, 3, 3),
  /* 1100 */ V(3, 10, 4),
  /* 1101 */ V(5, 9, 4),
  /* 1110 */ V(2, 10, 3),
  /* 1111 */ V(2, 10, 3),

  /* 0001 0000 ... */
  /* 0000 */ V(9, 5, 4),	/* 192 */
  /* 0001 */ V(6, 8, 4),
  /* 0010 */ V(10, 1, 3),
  /* 0011 */ V(10, 1, 3),
  /* 0100 */ V(8, 6, 4),
  /* 0101 */ V(7, 7, 4),
  /* 0110 */ V(9, 4, 3),
  /* 0111 */ V(9, 4, 3),
  /* 1000 */ V(4, 9, 4),
  /* 1001 */ V(5, 7, 4),
  /* 1010 */ V(6, 7, 3),
  /* 1011 */ V(6, 7, 3),
  /* 1100 */ V(10, 2, 2),
  /* 1101 */ V(10, 2, 2),
  /* 1110 */ V(10, 2, 2),
  /* 1111 */ V(10, 2, 2),

  /* 0001 0001 ... */
  /* 000  */ V(1, 10, 2),	/* 208 */
  /* 001  */ V(1, 10, 2),
  /* 010  */ V(0, 10, 3),
  /* 011  */ V(10, 0, 3),
  /* 100  */ V(3, 9, 3),
  /* 101  */ V(9, 3, 3),
  /* 110  */ V(5, 8, 3),
  /* 111  */ V(8, 5, 3),

  /* 0001 0010 ... */
  /* 000  */ V(2, 9, 2),	/* 216 */
  /* 001  */ V(2, 9, 2),
  /* 010  */ V(9, 2, 2),
  /* 011  */ V(9, 2, 2),
  /* 100  */ V(7, 6, 3),
  /* 101  */ V(0, 9, 3),
  /* 110  */ V(1, 9, 2),
  /* 111  */ V(1, 9, 2),

  /* 0001 0011 ... */
  /* 000  */ V(9, 1, 2),	/* 224 */
  /* 001  */ V(9, 1, 2),
  /* 010  */ V(9, 0, 3),
  /* 011  */ V(4, 8, 3),
  /* 100  */ V(8, 4, 3),
  /* 101  */ V(7, 5, 3),
  /* 110  */ V(3, 8, 3),
  /* 111  */ V(8, 3, 3),

  /* 0001 0100 ... */
  /* 000  */ V(6, 6, 3),	/* 232 */
  /* 001  */ V(2, 8, 3),
  /* 010  */ V(8, 2, 2),
  /* 011  */ V(8, 2, 2),
  /* 100  */ V(4, 7, 3),
  /* 101  */ V(7, 4, 3),
  /* 110  */ V(1, 8, 2),
  /* 111  */ V(1, 8, 2),

  /* 0001 0101 ... */
  /* 000  */ V(8, 1, 2),	/* 240 */
  /* 001  */ V(8, 1, 2),
  /* 010  */ V(8, 0, 2),
  /* 011  */ V(8, 0, 2),
  /* 100  */ V(0, 8, 3),
  /* 101  */ V(5, 6, 3),
  /* 110  */ V(3, 7, 2),
  /* 111  */ V(3, 7, 2),

  /* 0001 0110 ... */
  /* 000  */ V(7, 3, 2),	/* 248 */
  /* 001  */ V(7, 3, 2),
  /* 010  */ V(6, 5, 3),
  /* 011  */ V(4, 6, 3),
  /* 100  */ V(2, 7, 2),
  /* 101  */ V(2, 7, 2),
  /* 110  */ V(7, 2, 2),
  /* 111  */ V(7, 2, 2),

  /* 0001 0111 ... */
  /* 000  */ V(6, 4, 3),	/* 256 */
  /* 001  */ V(5, 5, 3),
  /* 010  */ V(0, 7, 2),
  /* 011  */ V(0, 7, 2),
  /* 100  */ V(1, 7, 1),
  /* 101  */ V(1, 7, 1),
  /* 110  */ V(1, 7, 1),
  /* 111  */ V(1, 7, 1),

  /* 0001 1000 ... */
  /* 00   */ V(7, 1, 1),	/* 264  */
  /* 01   */ V(7, 1, 1),
  /* 10   */ V(7, 0, 2),
  /* 11   */ V(3, 6, 2),

  /* 0001 1001 ... */
  /* 00   */ V(6, 3, 2),	/* 268 */
  /* 01   */ V(4, 5, 2),
  /* 10   */ V(5, 4, 2),
  /* 11   */ V(2, 6, 2),

  /* 0001 1010 ... */
  /* 0    */ V(6, 2, 1),	/* 272 */
  /* 1    */ V(1, 6, 1),

  /* 0001 1011 ... */
  /* 00   */ V(6, 1, 1),	/* 274 */
  /* 01   */ V(6, 1, 1),
  /* 10   */ V(0, 6, 2),
  /* 11   */ V(6, 0, 2),

  /* 0001 1100 ... */
  /* 00   */ V(5, 3, 1),	/* 278 */
  /* 01   */ V(5, 3, 1),
  /* 10   */ V(3, 5, 2),
  /* 11   */ V(4, 4, 2),

  /* 0001 1101 ... */
  /* 0    */ V(2, 5, 1),	/* 282 */
  /* 1    */ V(5, 2, 1),

  /* 0001 1111 ... */
  /* 0    */ V(1, 5, 1),	/* 284 */
  /* 1    */ V(0, 5, 1),

  /* 0010 0000 ... */
  /* 0    */ V(3, 4, 1),	/* 286 */
  /* 1    */ V(4, 3, 1),

  /* 0010 0001 ... */
  /* 0    */ V(5, 0, 1),	/* 288 */
  /* 1    */ V(2, 4, 1),

  /* 0010 0010 ... */
  /* 0    */ V(4, 2, 1),	/* 290 */
  /* 1    */ V(3, 3, 1),

  /* 0010 0101 ... */
  /* 0    */ V(0, 4, 1),	/* 292 */
  /* 1    */ V(4, 0, 1),

  /* 0000 0110 1100 ... */
  /* 0000 */ V(12, 14, 4),	/* 294 */
  /* 0001 */ PTR(400, 1),
  /* 0010 */ V(13, 14, 3),
  /* 0011 */ V(13, 14, 3),
  /* 0100 */ V(14, 9, 3),
  /* 0101 */ V(14, 9, 3),
  /* 0110 */ V(14, 10, 4),
  /* 0111 */ V(13, 9, 4),
  /* 1000 */ V(14, 14, 2),
  /* 1001 */ V(14, 14, 2),
  /* 1010 */ V(14, 14, 2),
  /* 1011 */ V(14, 14, 2),
  /* 1100 */ V(14, 13, 3),
  /* 1101 */ V(14, 13, 3),
  /* 1110 */ V(14, 11, 3),
  /* 1111 */ V(14, 11, 3),

  /* 0000 0110 1101 ... */
  /* 000  */ V(11, 14, 2),	/* 310 */
  /* 001  */ V(11, 14, 2),
  /* 010  */ V(12, 13, 2),
  /* 011  */ V(12, 13, 2),
  /* 100  */ V(13, 12, 3),
  /* 101  */ V(13, 11, 3),
  /* 110  */ V(10, 14, 2),
  /* 111  */ V(10, 14, 2),

  /* 0000 0110 1110 ... */
  /* 000  */ V(12, 12, 2),	/* 318 */
  /* 001  */ V(12, 12, 2),
  /* 010  */ V(10, 13, 3),
  /* 011  */ V(13, 10, 3),
  /* 100  */ V(7, 14, 3),
  /* 101  */ V(10, 12, 3),
  /* 110  */ V(12, 10, 2),
  /* 111  */ V(12, 10, 2),

  /* 0000 0110 1111 ... */
  /* 000  */ V(12, 9, 3),	/* 326 */
  /* 001  */ V(7, 13, 3),
  /* 010  */ V(5, 14, 2),
  /* 011  */ V(5, 14, 2),
  /* 100  */ V(11, 13, 1),
  /* 101  */ V(11, 13, 1),
  /* 110  */ V(11, 13, 1),
  /* 111  */ V(11, 13, 1),

  /* 0000 1011 0000 ... */
  /* 00   */ V(9, 14, 1),	/* 334 */
  /* 01   */ V(9, 14, 1),
  /* 10   */ V(11, 12, 2),
  /* 11   */ V(12, 11, 2),

  /* 0000 1011 0001 ... */
  /* 00   */ V(8, 14, 2),	/* 338 */
  /* 01   */ V(14, 8, 2),
  /* 10   */ V(9, 13, 2),
  /* 11   */ V(14, 7, 2),

  /* 0000 1011 0010 ... */
  /* 00   */ V(11, 11, 2),	/* 342 */
  /* 01   */ V(8, 13, 2),
  /* 10   */ V(13, 8, 2),
  /* 11   */ V(6, 14, 2),

  /* 0000 1011 0011 ... */
  /* 0    */ V(14, 6, 1),	/* 346 */
  /* 1    */ V(9, 12, 1),

  /* 0000 1011 0100 ... */
  /* 00   */ V(10, 11, 2),	/* 348 */
  /* 01   */ V(11, 10, 2),
  /* 10   */ V(14, 5, 2),
  /* 11   */ V(13, 7, 2),

  /* 0000 1011 0101 ... */
  /* 00   */ V(4, 14, 1),	/* 352 */
  /* 01   */ V(4, 14, 1),
  /* 10   */ V(14, 4, 2),
  /* 11   */ V(8, 12, 2),

  /* 0000 1011 0110 ... */
  /* 0    */ V(12, 8, 1),	/* 356 */
  /* 1    */ V(3, 14, 1),

  /* 0000 1011 0111 ... */
  /* 00   */ V(6, 13, 1),	/* 358 */
  /* 01   */ V(6, 13, 1),
  /* 10   */ V(13, 6, 2),
  /* 11   */ V(9, 11, 2),

  /* 0000 1011 1000 ... */
  /* 00   */ V(11, 9, 2),	/* 362 */
  /* 01   */ V(10, 10, 2),
  /* 10   */ V(14, 1, 1),
  /* 11   */ V(14, 1, 1),

  /* 0000 1011 1001 ... */
  /* 00   */ V(13, 4, 1),	/* 366 */
  /* 01   */ V(13, 4, 1),
  /* 10   */ V(11, 8, 2),
  /* 11   */ V(10, 9, 2),

  /* 0000 1011 1010 ... */
  /* 00   */ V(7, 11, 1),	/* 370 */
  /* 01   */ V(7, 11, 1),
  /* 10   */ V(11, 7, 2),
  /* 11   */ V(13, 0, 2),

  /* 0000 1011 1100 ... */
  /* 0    */ V(0, 14, 1),	/* 374 */
  /* 1    */ V(14, 0, 1),

  /* 0000 1011 1101 ... */
  /* 0    */ V(5, 13, 1),	/* 376 */
  /* 1    */ V(13, 5, 1),

  /* 0000 1011 1110 ... */
  /* 0    */ V(7, 12, 1),	/* 378 */
  /* 1    */ V(12, 7, 1),

  /* 0000 1011 1111 ... */
  /* 0    */ V(4, 13, 1),	/* 380 */
  /* 1    */ V(8, 11, 1),

  /* 0000 1100 0000 ... */
  /* 0    */ V(9, 10, 1),	/* 382 */
  /* 1    */ V(6, 12, 1),

  /* 0000 1100 0001 ... */
  /* 0    */ V(12, 6, 1),	/* 384 */
  /* 1    */ V(3, 13, 1),

  /* 0000 1100 0010 ... */
  /* 0    */ V(5, 12, 1),	/* 386 */
  /* 1    */ V(12, 5, 1),

  /* 0000 1100 0100 ... */
  /* 0    */ V(8, 10, 1),	/* 388 */
  /* 1    */ V(10, 8, 1),

  /* 0000 1100 0101 ... */
  /* 0    */ V(9, 9, 1),	/* 390 */
  /* 1    */ V(4, 12, 1),

  /* 0000 1100 0110 ... */
  /* 0    */ V(11, 6, 1),	/* 392 */
  /* 1    */ V(7, 10, 1),

  /* 0000 1100 1000 ... */
  /* 0    */ V(5, 11, 1),	/* 394 */
  /* 1    */ V(8, 9, 1),

  /* 0000 1100 1011 ... */
  /* 0    */ V(9, 8, 1),	/* 396 */
  /* 1    */ V(7, 9, 1),

  /* 0000 1101 0101 ... */
  /* 0    */ V(9, 7, 1),	/* 398 */
  /* 1    */ V(8, 8, 1),

  /* 0000 0110 1100 0001 ... */
  /* 0    */ V(14, 12, 1),	/* 400 */
  /* 1    */ V(13, 13, 1)
];

const hufftab24 = [
  /* 0000 */ PTR(16, 4),
  /* 0001 */ PTR(32, 4),
  /* 0010 */ PTR(48, 4),
  /* 0011 */ V(15, 15, 4),
  /* 0100 */ PTR(64, 4),
  /* 0101 */ PTR(80, 4),
  /* 0110 */ PTR(96, 4),
  /* 0111 */ PTR(112, 4),
  /* 1000 */ PTR(128, 4),
  /* 1001 */ PTR(144, 4),
  /* 1010 */ PTR(160, 3),
  /* 1011 */ PTR(168, 2),
  /* 1100 */ V(1, 1, 4),
  /* 1101 */ V(0, 1, 4),
  /* 1110 */ V(1, 0, 4),
  /* 1111 */ V(0, 0, 4),

  /* 0000 ... */
  /* 0000 */ V(14, 15, 4),	/* 16 */
  /* 0001 */ V(15, 14, 4),
  /* 0010 */ V(13, 15, 4),
  /* 0011 */ V(15, 13, 4),
  /* 0100 */ V(12, 15, 4),
  /* 0101 */ V(15, 12, 4),
  /* 0110 */ V(11, 15, 4),
  /* 0111 */ V(15, 11, 4),
  /* 1000 */ V(15, 10, 3),
  /* 1001 */ V(15, 10, 3),
  /* 1010 */ V(10, 15, 4),
  /* 1011 */ V(9, 15, 4),
  /* 1100 */ V(15, 9, 3),
  /* 1101 */ V(15, 9, 3),
  /* 1110 */ V(15, 8, 3),
  /* 1111 */ V(15, 8, 3),

  /* 0001 ... */
  /* 0000 */ V(8, 15, 4),	/* 32 */
  /* 0001 */ V(7, 15, 4),
  /* 0010 */ V(15, 7, 3),
  /* 0011 */ V(15, 7, 3),
  /* 0100 */ V(6, 15, 3),
  /* 0101 */ V(6, 15, 3),
  /* 0110 */ V(15, 6, 3),
  /* 0111 */ V(15, 6, 3),
  /* 1000 */ V(5, 15, 3),
  /* 1001 */ V(5, 15, 3),
  /* 1010 */ V(15, 5, 3),
  /* 1011 */ V(15, 5, 3),
  /* 1100 */ V(4, 15, 3),
  /* 1101 */ V(4, 15, 3),
  /* 1110 */ V(15, 4, 3),
  /* 1111 */ V(15, 4, 3),

  /* 0010 ... */
  /* 0000 */ V(3, 15, 3),	/* 48 */
  /* 0001 */ V(3, 15, 3),
  /* 0010 */ V(15, 3, 3),
  /* 0011 */ V(15, 3, 3),
  /* 0100 */ V(2, 15, 3),
  /* 0101 */ V(2, 15, 3),
  /* 0110 */ V(15, 2, 3),
  /* 0111 */ V(15, 2, 3),
  /* 1000 */ V(15, 1, 3),
  /* 1001 */ V(15, 1, 3),
  /* 1010 */ V(1, 15, 4),
  /* 1011 */ V(15, 0, 4),
  /* 1100 */ PTR(172, 3),
  /* 1101 */ PTR(180, 3),
  /* 1110 */ PTR(188, 3),
  /* 1111 */ PTR(196, 3),

  /* 0100 ... */
  /* 0000 */ PTR(204, 4),	/* 64 */
  /* 0001 */ PTR(220, 3),
  /* 0010 */ PTR(228, 3),
  /* 0011 */ PTR(236, 3),
  /* 0100 */ PTR(244, 2),
  /* 0101 */ PTR(248, 2),
  /* 0110 */ PTR(252, 2),
  /* 0111 */ PTR(256, 2),
  /* 1000 */ PTR(260, 2),
  /* 1001 */ PTR(264, 2),
  /* 1010 */ PTR(268, 2),
  /* 1011 */ PTR(272, 2),
  /* 1100 */ PTR(276, 2),
  /* 1101 */ PTR(280, 3),
  /* 1110 */ PTR(288, 2),
  /* 1111 */ PTR(292, 2),

  /* 0101 ... */
  /* 0000 */ PTR(296, 2),	/* 80 */
  /* 0001 */ PTR(300, 3),
  /* 0010 */ PTR(308, 2),
  /* 0011 */ PTR(312, 3),
  /* 0100 */ PTR(320, 1),
  /* 0101 */ PTR(322, 2),
  /* 0110 */ PTR(326, 2),
  /* 0111 */ PTR(330, 1),
  /* 1000 */ PTR(332, 2),
  /* 1001 */ PTR(336, 1),
  /* 1010 */ PTR(338, 1),
  /* 1011 */ PTR(340, 1),
  /* 1100 */ PTR(342, 1),
  /* 1101 */ PTR(344, 1),
  /* 1110 */ PTR(346, 1),
  /* 1111 */ PTR(348, 1),

  /* 0110 ... */
  /* 0000 */ PTR(350, 1),	/* 96 */
  /* 0001 */ PTR(352, 1),
  /* 0010 */ PTR(354, 1),
  /* 0011 */ PTR(356, 1),
  /* 0100 */ PTR(358, 1),
  /* 0101 */ PTR(360, 1),
  /* 0110 */ PTR(362, 1),
  /* 0111 */ PTR(364, 1),
  /* 1000 */ PTR(366, 1),
  /* 1001 */ PTR(368, 1),
  /* 1010 */ PTR(370, 2),
  /* 1011 */ PTR(374, 1),
  /* 1100 */ PTR(376, 2),
  /* 1101 */ V(7, 3, 4),
  /* 1110 */ PTR(380, 1),
  /* 1111 */ V(7, 2, 4),

  /* 0111 ... */
  /* 0000 */ V(4, 6, 4),	/* 112 */
  /* 0001 */ V(6, 4, 4),
  /* 0010 */ V(5, 5, 4),
  /* 0011 */ V(7, 1, 4),
  /* 0100 */ V(3, 6, 4),
  /* 0101 */ V(6, 3, 4),
  /* 0110 */ V(4, 5, 4),
  /* 0111 */ V(5, 4, 4),
  /* 1000 */ V(2, 6, 4),
  /* 1001 */ V(6, 2, 4),
  /* 1010 */ V(1, 6, 4),
  /* 1011 */ V(6, 1, 4),
  /* 1100 */ PTR(382, 1),
  /* 1101 */ V(3, 5, 4),
  /* 1110 */ V(5, 3, 4),
  /* 1111 */ V(4, 4, 4),

  /* 1000 ... */
  /* 0000 */ V(2, 5, 4),	/* 128 */
  /* 0001 */ V(5, 2, 4),
  /* 0010 */ V(1, 5, 4),
  /* 0011 */ PTR(384, 1),
  /* 0100 */ V(5, 1, 3),
  /* 0101 */ V(5, 1, 3),
  /* 0110 */ V(3, 4, 4),
  /* 0111 */ V(4, 3, 4),
  /* 1000 */ V(2, 4, 3),
  /* 1001 */ V(2, 4, 3),
  /* 1010 */ V(4, 2, 3),
  /* 1011 */ V(4, 2, 3),
  /* 1100 */ V(3, 3, 3),
  /* 1101 */ V(3, 3, 3),
  /* 1110 */ V(1, 4, 3),
  /* 1111 */ V(1, 4, 3),

  /* 1001 ... */
  /* 0000 */ V(4, 1, 3),	/* 144 */
  /* 0001 */ V(4, 1, 3),
  /* 0010 */ V(0, 4, 4),
  /* 0011 */ V(4, 0, 4),
  /* 0100 */ V(2, 3, 3),
  /* 0101 */ V(2, 3, 3),
  /* 0110 */ V(3, 2, 3),
  /* 0111 */ V(3, 2, 3),
  /* 1000 */ V(1, 3, 2),
  /* 1001 */ V(1, 3, 2),
  /* 1010 */ V(1, 3, 2),
  /* 1011 */ V(1, 3, 2),
  /* 1100 */ V(3, 1, 2),
  /* 1101 */ V(3, 1, 2),
  /* 1110 */ V(3, 1, 2),
  /* 1111 */ V(3, 1, 2),

  /* 1010 ... */
  /* 000  */ V(0, 3, 3),	/* 160 */
  /* 001  */ V(3, 0, 3),
  /* 010  */ V(2, 2, 2),
  /* 011  */ V(2, 2, 2),
  /* 100  */ V(1, 2, 1),
  /* 101  */ V(1, 2, 1),
  /* 110  */ V(1, 2, 1),
  /* 111  */ V(1, 2, 1),

  /* 1011 ... */
  /* 00   */ V(2, 1, 1),	/* 168 */
  /* 01   */ V(2, 1, 1),
  /* 10   */ V(0, 2, 2),
  /* 11   */ V(2, 0, 2),

  /* 0010 1100 ... */
  /* 000  */ V(0, 15, 1),	/* 172 */
  /* 001  */ V(0, 15, 1),
  /* 010  */ V(0, 15, 1),
  /* 011  */ V(0, 15, 1),
  /* 100  */ V(14, 14, 3),
  /* 101  */ V(13, 14, 3),
  /* 110  */ V(14, 13, 3),
  /* 111  */ V(12, 14, 3),

  /* 0010 1101 ... */
  /* 000  */ V(14, 12, 3),	/* 180 */
  /* 001  */ V(13, 13, 3),
  /* 010  */ V(11, 14, 3),
  /* 011  */ V(14, 11, 3),
  /* 100  */ V(12, 13, 3),
  /* 101  */ V(13, 12, 3),
  /* 110  */ V(10, 14, 3),
  /* 111  */ V(14, 10, 3),

  /* 0010 1110 ... */
  /* 000  */ V(11, 13, 3),	/* 188 */
  /* 001  */ V(13, 11, 3),
  /* 010  */ V(12, 12, 3),
  /* 011  */ V(9, 14, 3),
  /* 100  */ V(14, 9, 3),
  /* 101  */ V(10, 13, 3),
  /* 110  */ V(13, 10, 3),
  /* 111  */ V(11, 12, 3),

  /* 0010 1111 ... */
  /* 000  */ V(12, 11, 3),	/* 196 */
  /* 001  */ V(8, 14, 3),
  /* 010  */ V(14, 8, 3),
  /* 011  */ V(9, 13, 3),
  /* 100  */ V(13, 9, 3),
  /* 101  */ V(7, 14, 3),
  /* 110  */ V(14, 7, 3),
  /* 111  */ V(10, 12, 3),

  /* 0100 0000 ... */
  /* 0000 */ V(12, 10, 3),	/* 204 */
  /* 0001 */ V(12, 10, 3),
  /* 0010 */ V(11, 11, 3),
  /* 0011 */ V(11, 11, 3),
  /* 0100 */ V(8, 13, 3),
  /* 0101 */ V(8, 13, 3),
  /* 0110 */ V(13, 8, 3),
  /* 0111 */ V(13, 8, 3),
  /* 1000 */ V(0, 14, 4),
  /* 1001 */ V(14, 0, 4),
  /* 1010 */ V(0, 13, 3),
  /* 1011 */ V(0, 13, 3),
  /* 1100 */ V(14, 6, 2),
  /* 1101 */ V(14, 6, 2),
  /* 1110 */ V(14, 6, 2),
  /* 1111 */ V(14, 6, 2),

  /* 0100 0001 ... */
  /* 000  */ V(6, 14, 3),	/* 220 */
  /* 001  */ V(9, 12, 3),
  /* 010  */ V(12, 9, 2),
  /* 011  */ V(12, 9, 2),
  /* 100  */ V(5, 14, 2),
  /* 101  */ V(5, 14, 2),
  /* 110  */ V(11, 10, 2),
  /* 111  */ V(11, 10, 2),

  /* 0100 0010 ... */
  /* 000  */ V(14, 5, 2),	/* 228 */
  /* 001  */ V(14, 5, 2),
  /* 010  */ V(10, 11, 3),
  /* 011  */ V(7, 13, 3),
  /* 100  */ V(13, 7, 2),
  /* 101  */ V(13, 7, 2),
  /* 110  */ V(14, 4, 2),
  /* 111  */ V(14, 4, 2),

  /* 0100 0011 ... */
  /* 000  */ V(8, 12, 2),	/* 236 */
  /* 001  */ V(8, 12, 2),
  /* 010  */ V(12, 8, 2),
  /* 011  */ V(12, 8, 2),
  /* 100  */ V(4, 14, 3),
  /* 101  */ V(2, 14, 3),
  /* 110  */ V(3, 14, 2),
  /* 111  */ V(3, 14, 2),

  /* 0100 0100 ... */
  /* 00   */ V(6, 13, 2),	/* 244 */
  /* 01   */ V(13, 6, 2),
  /* 10   */ V(14, 3, 2),
  /* 11   */ V(9, 11, 2),

  /* 0100 0101 ... */
  /* 00   */ V(11, 9, 2),	/* 248 */
  /* 01   */ V(10, 10, 2),
  /* 10   */ V(14, 2, 2),
  /* 11   */ V(1, 14, 2),

  /* 0100 0110 ... */
  /* 00   */ V(14, 1, 2),	/* 252 */
  /* 01   */ V(5, 13, 2),
  /* 10   */ V(13, 5, 2),
  /* 11   */ V(7, 12, 2),

  /* 0100 0111 ... */
  /* 00   */ V(12, 7, 2),	/* 256 */
  /* 01   */ V(4, 13, 2),
  /* 10   */ V(8, 11, 2),
  /* 11   */ V(11, 8, 2),

  /* 0100 1000 ... */
  /* 00   */ V(13, 4, 2),	/* 260 */
  /* 01   */ V(9, 10, 2),
  /* 10   */ V(10, 9, 2),
  /* 11   */ V(6, 12, 2),

  /* 0100 1001 ... */
  /* 00   */ V(12, 6, 2),	/* 264 */
  /* 01   */ V(3, 13, 2),
  /* 10   */ V(13, 3, 2),
  /* 11   */ V(2, 13, 2),

  /* 0100 1010 ... */
  /* 00   */ V(13, 2, 2),	/* 268 */
  /* 01   */ V(1, 13, 2),
  /* 10   */ V(7, 11, 2),
  /* 11   */ V(11, 7, 2),

  /* 0100 1011 ... */
  /* 00   */ V(13, 1, 2),	/* 272 */
  /* 01   */ V(5, 12, 2),
  /* 10   */ V(12, 5, 2),
  /* 11   */ V(8, 10, 2),

  /* 0100 1100 ... */
  /* 00   */ V(10, 8, 2),	/* 276 */
  /* 01   */ V(9, 9, 2),
  /* 10   */ V(4, 12, 2),
  /* 11   */ V(12, 4, 2),

  /* 0100 1101 ... */
  /* 000  */ V(6, 11, 2),	/* 280 */
  /* 001  */ V(6, 11, 2),
  /* 010  */ V(11, 6, 2),
  /* 011  */ V(11, 6, 2),
  /* 100  */ V(13, 0, 3),
  /* 101  */ V(0, 12, 3),
  /* 110  */ V(3, 12, 2),
  /* 111  */ V(3, 12, 2),

  /* 0100 1110 ... */
  /* 00   */ V(12, 3, 2),	/* 288 */
  /* 01   */ V(7, 10, 2),
  /* 10   */ V(10, 7, 2),
  /* 11   */ V(2, 12, 2),

  /* 0100 1111 ... */
  /* 00   */ V(12, 2, 2),	/* 292 */
  /* 01   */ V(5, 11, 2),
  /* 10   */ V(11, 5, 2),
  /* 11   */ V(1, 12, 2),

  /* 0101 0000 ... */
  /* 00   */ V(8, 9, 2),	/* 296 */
  /* 01   */ V(9, 8, 2),
  /* 10   */ V(12, 1, 2),
  /* 11   */ V(4, 11, 2),

  /* 0101 0001 ... */
  /* 000  */ V(12, 0, 3),	/* 300 */
  /* 001  */ V(0, 11, 3),
  /* 010  */ V(3, 11, 2),
  /* 011  */ V(3, 11, 2),
  /* 100  */ V(11, 0, 3),
  /* 101  */ V(0, 10, 3),
  /* 110  */ V(1, 10, 2),
  /* 111  */ V(1, 10, 2),

  /* 0101 0010 ... */
  /* 00   */ V(11, 4, 1),	/* 308 */
  /* 01   */ V(11, 4, 1),
  /* 10   */ V(6, 10, 2),
  /* 11   */ V(10, 6, 2),

  /* 0101 0011 ... */
  /* 000  */ V(7, 9, 2),	/* 312 */
  /* 001  */ V(7, 9, 2),
  /* 010  */ V(9, 7, 2),
  /* 011  */ V(9, 7, 2),
  /* 100  */ V(10, 0, 3),
  /* 101  */ V(0, 9, 3),
  /* 110  */ V(9, 0, 2),
  /* 111  */ V(9, 0, 2),

  /* 0101 0100 ... */
  /* 0    */ V(11, 3, 1),	/* 320 */
  /* 1    */ V(8, 8, 1),

  /* 0101 0101 ... */
  /* 00   */ V(2, 11, 2),	/* 322 */
  /* 01   */ V(5, 10, 2),
  /* 10   */ V(11, 2, 1),
  /* 11   */ V(11, 2, 1),

  /* 0101 0110 ... */
  /* 00   */ V(10, 5, 2),	/* 326 */
  /* 01   */ V(1, 11, 2),
  /* 10   */ V(11, 1, 2),
  /* 11   */ V(6, 9, 2),

  /* 0101 0111 ... */
  /* 0    */ V(9, 6, 1),	/* 330 */
  /* 1    */ V(10, 4, 1),

  /* 0101 1000 ... */
  /* 00   */ V(4, 10, 2),	/* 332 */
  /* 01   */ V(7, 8, 2),
  /* 10   */ V(8, 7, 1),
  /* 11   */ V(8, 7, 1),

  /* 0101 1001 ... */
  /* 0    */ V(3, 10, 1),	/* 336 */
  /* 1    */ V(10, 3, 1),

  /* 0101 1010 ... */
  /* 0    */ V(5, 9, 1),	/* 338 */
  /* 1    */ V(9, 5, 1),

  /* 0101 1011 ... */
  /* 0    */ V(2, 10, 1),	/* 340 */
  /* 1    */ V(10, 2, 1),

  /* 0101 1100 ... */
  /* 0    */ V(10, 1, 1),	/* 342 */
  /* 1    */ V(6, 8, 1),

  /* 0101 1101 ... */
  /* 0    */ V(8, 6, 1),	/* 344 */
  /* 1    */ V(7, 7, 1),

  /* 0101 1110 ... */
  /* 0    */ V(4, 9, 1),	/* 346 */
  /* 1    */ V(9, 4, 1),

  /* 0101 1111 ... */
  /* 0    */ V(3, 9, 1),	/* 348 */
  /* 1    */ V(9, 3, 1),

  /* 0110 0000 ... */
  /* 0    */ V(5, 8, 1),	/* 350 */
  /* 1    */ V(8, 5, 1),

  /* 0110 0001 ... */
  /* 0    */ V(2, 9, 1),	/* 352 */
  /* 1    */ V(6, 7, 1),

  /* 0110 0010 ... */
  /* 0    */ V(7, 6, 1),	/* 354 */
  /* 1    */ V(9, 2, 1),

  /* 0110 0011 ... */
  /* 0    */ V(1, 9, 1),	/* 356 */
  /* 1    */ V(9, 1, 1),

  /* 0110 0100 ... */
  /* 0    */ V(4, 8, 1),	/* 358 */
  /* 1    */ V(8, 4, 1),

  /* 0110 0101 ... */
  /* 0    */ V(5, 7, 1),	/* 360 */
  /* 1    */ V(7, 5, 1),

  /* 0110 0110 ... */
  /* 0    */ V(3, 8, 1),	/* 362 */
  /* 1    */ V(8, 3, 1),

  /* 0110 0111 ... */
  /* 0    */ V(6, 6, 1),	/* 364 */
  /* 1    */ V(2, 8, 1),

  /* 0110 1000 ... */
  /* 0    */ V(8, 2, 1),	/* 366 */
  /* 1    */ V(1, 8, 1),

  /* 0110 1001 ... */
  /* 0    */ V(4, 7, 1),	/* 368 */
  /* 1    */ V(7, 4, 1),

  /* 0110 1010 ... */
  /* 00   */ V(8, 1, 1),	/* 370 */
  /* 01   */ V(8, 1, 1),
  /* 10   */ V(0, 8, 2),
  /* 11   */ V(8, 0, 2),

  /* 0110 1011 ... */
  /* 0    */ V(5, 6, 1),	/* 374 */
  /* 1    */ V(6, 5, 1),

  /* 0110 1100 ... */
  /* 00   */ V(1, 7, 1),	/* 376 */
  /* 01   */ V(1, 7, 1),
  /* 10   */ V(0, 7, 2),
  /* 11   */ V(7, 0, 2),

  /* 0110 1110 ... */
  /* 0    */ V(3, 7, 1),	/* 380  */
  /* 1    */ V(2, 7, 1),

  /* 0111 1100 ... */
  /* 0    */ V(0, 6, 1),	/* 382 */
  /* 1    */ V(6, 0, 1),

  /* 1000 0011 ... */
  /* 0    */ V(0, 5, 1),	/* 384 */
  /* 1    */ V(5, 0, 1)
];

/* hufftable constructor */
function MP3Hufftable(table, linbits, startbits) {
    this.table = table;
    this.linbits = linbits;
    this.startbits = startbits;
};

/* external tables */
exports.huff_quad_table = [ hufftabA, hufftabB ];
exports.huff_pair_table = [
  /*  0 */ new MP3Hufftable(hufftab0,   0, 0),
  /*  1 */ new MP3Hufftable(hufftab1,   0, 3),
  /*  2 */ new MP3Hufftable(hufftab2,   0, 3),
  /*  3 */ new MP3Hufftable(hufftab3,   0, 3),
  /*  4 */ null, //new MP3Hufftable(0 /* not used */),
  /*  5 */ new MP3Hufftable(hufftab5,   0, 3),
  /*  6 */ new MP3Hufftable(hufftab6,   0, 4),
  /*  7 */ new MP3Hufftable(hufftab7,   0, 4),
  /*  8 */ new MP3Hufftable(hufftab8,   0, 4),
  /*  9 */ new MP3Hufftable(hufftab9,   0, 4),
  /* 10 */ new MP3Hufftable(hufftab10,  0, 4),
  /* 11 */ new MP3Hufftable(hufftab11,  0, 4),
  /* 12 */ new MP3Hufftable(hufftab12,  0, 4),
  /* 13 */ new MP3Hufftable(hufftab13,  0, 4),
  /* 14 */ null, //new MP3Hufftable(0 /* not used */),
  /* 15 */ new MP3Hufftable(hufftab15,  0, 4),
  /* 16 */ new MP3Hufftable(hufftab16,  1, 4),
  /* 17 */ new MP3Hufftable(hufftab16,  2, 4),
  /* 18 */ new MP3Hufftable(hufftab16,  3, 4),
  /* 19 */ new MP3Hufftable(hufftab16,  4, 4),
  /* 20 */ new MP3Hufftable(hufftab16,  6, 4),
  /* 21 */ new MP3Hufftable(hufftab16,  8, 4),
  /* 22 */ new MP3Hufftable(hufftab16, 10, 4),
  /* 23 */ new MP3Hufftable(hufftab16, 13, 4),
  /* 24 */ new MP3Hufftable(hufftab24,  4, 4),
  /* 25 */ new MP3Hufftable(hufftab24,  5, 4),
  /* 26 */ new MP3Hufftable(hufftab24,  6, 4),
  /* 27 */ new MP3Hufftable(hufftab24,  7, 4),
  /* 28 */ new MP3Hufftable(hufftab24,  8, 4),
  /* 29 */ new MP3Hufftable(hufftab24,  9, 4),
  /* 30 */ new MP3Hufftable(hufftab24, 11, 4),
  /* 31 */ new MP3Hufftable(hufftab24, 13, 4)
];

},{}],7:[function(require,module,exports){
var AV = (window.AV);

const ENCODINGS = ['latin1', 'utf16-bom', 'utf16-be', 'utf8'];

var ID3Stream = AV.Base.extend({
    constructor: function(header, stream) {
        this.header = header;
        this.stream = stream;
        this.offset = 0;
    },
    
    read: function() {
        if (!this.data) {
            this.data = {};
            
            // read all frames
            var frame;
            while (frame = this.readFrame()) {
                // if we already have an instance of this key, add it to an array
                if (frame.key in this.data) {
                    if (!Array.isArray(this.data[frame.key]))
                        this.data[frame.key] = [this.data[frame.key]];
                        
                    this.data[frame.key].push(frame.value);
                } else {
                    this.data[frame.key] = frame.value;
                }
            }
        }

        return this.data;
    },
    
    readFrame: function() {
        if (this.offset >= this.header.length)
            return null;
        
        // get the header    
        var header = this.readHeader();
        var decoder = header.identifier;
        
        if (header.identifier.charCodeAt(0) === 0) {
            this.offset += this.header.length + 1;
            return null;
        }
        
        // map common frame names to a single type
        if (!this.frameTypes[decoder]) {
            for (var key in this.map) {
                if (this.map[key].indexOf(decoder) !== -1) {
                    decoder = key;
                    break;
                }
            }
        }

        if (this.frameTypes[decoder]) {
            // decode the frame
            var frame = this.decodeFrame(header, this.frameTypes[decoder]),
                keys = Object.keys(frame);
            
            // if it only returned one key, use that as the value    
            if (keys.length === 1)
                frame = frame[keys[0]];
            
            var result = {
                value: frame
            };
            
        } else {
            // No frame type found, treat it as binary
            var result = {
                value: this.stream.readBuffer(Math.min(header.length, this.header.length - this.offset))
            };
        }

        result.key = this.names[header.identifier] ? this.names[header.identifier] : header.identifier;
        
        // special sauce for cover art, which should just be a buffer
        if (result.key === 'coverArt')
            result.value = result.value.data;

        this.offset += 10 + header.length;
        return result;
    },

    decodeFrame: function(header, fields) {
        var stream = this.stream,
            start = stream.offset;
            
        var encoding = 0, ret = {};
        var len = Object.keys(fields).length, i = 0;
        
        for (var key in fields) {
            var type = fields[key];
            var rest = header.length - (stream.offset - start);
            i++;
            
            // check for special field names
            switch (key) {
                case 'encoding':
                    encoding = stream.readUInt8();
                    continue;
                
                case 'language':
                    ret.language = stream.readString(3);
                    continue;
            }
            
            // check types
            switch (type) {                    
                case 'latin1':
                    ret[key] = stream.readString(i === len ? rest : null, 'latin1');
                    break;
                    
                case 'string':
                    ret[key] = stream.readString(i === len ? rest : null, ENCODINGS[encoding]);
                    break;
                    
                case 'binary':
                    ret[key] = stream.readBuffer(rest)
                    break;
                    
                case 'int16':
                    ret[key] = stream.readInt16();
                    break;
                    
                case 'int8':
                    ret[key] = stream.readInt8();
                    break;
                    
                case 'int24':
                    ret[key] = stream.readInt24();
                    break;
                    
                case 'int32':
                    ret[key] = stream.readInt32();
                    break;
                    
                case 'int32+':
                    ret[key] = stream.readInt32();
                    if (rest > 4)
                        throw new Error('Seriously dude? Stop playing this song and get a life!');
                        
                    break;
                    
                case 'date':
                    var val = stream.readString(8);
                    ret[key] = new Date(val.slice(0, 4), val.slice(4, 6) - 1, val.slice(6, 8));
                    break;
                    
                case 'frame_id':
                    ret[key] = stream.readString(4);
                    break;
                    
                default:
                    throw new Error('Unknown key type ' + type);
            }
        }
        
        // Just in case something went wrong...
        var rest = header.length - (stream.offset - start);
        if (rest > 0)
            stream.advance(rest);
        
        return ret;
    }
});

// ID3 v2.3 and v2.4 support
exports.ID3v23Stream = ID3Stream.extend({
    readHeader: function() {
        var identifier = this.stream.readString(4);        
        var length = 0;
        
        if (this.header.major === 4) {
            for (var i = 0; i < 4; i++)
                length = (length << 7) + (this.stream.readUInt8() & 0x7f);
        } else {
            length = this.stream.readUInt32();
        }
        
        return {
            identifier: identifier,
            length: length,
            flags: this.stream.readUInt16()
        };
    },
    
    map: {
        text: [
            // Identification Frames
            'TIT1', 'TIT2', 'TIT3', 'TALB', 'TOAL', 'TRCK', 'TPOS', 'TSST', 'TSRC',

            // Involved Persons Frames
            'TPE1', 'TPE2', 'TPE3', 'TPE4', 'TOPE', 'TEXT', 'TOLY', 'TCOM', 'TMCL', 'TIPL', 'TENC',

            // Derived and Subjective Properties Frames
            'TBPM', 'TLEN', 'TKEY', 'TLAN', 'TCON', 'TFLT', 'TMED', 'TMOO',

            // Rights and Licence Frames
            'TCOP', 'TPRO', 'TPUB', 'TOWN', 'TRSN', 'TRSO',

            // Other Text Frames
            'TOFN', 'TDLY', 'TDEN', 'TDOR', 'TDRC', 'TDRL', 'TDTG', 'TSSE', 'TSOA', 'TSOP', 'TSOT',
            
            // Deprecated Text Frames
            'TDAT', 'TIME', 'TORY', 'TRDA', 'TSIZ', 'TYER',
            
            // Non-standard iTunes Frames
            'TCMP', 'TSO2', 'TSOC'
        ],
        
        url: [
            'WCOM', 'WCOP', 'WOAF', 'WOAR', 'WOAS', 'WORS', 'WPAY', 'WPUB'
        ]
    },
    
    frameTypes: {        
        text: {
            encoding: 1,
            value: 'string'
        },
        
        url: {
            value: 'latin1'
        },
        
        TXXX: {
            encoding: 1,
            description: 'string',
            value: 'string'
        },
        
        WXXX: {
            encoding: 1,
            description: 'string',
            value: 'latin1',
        },
        
        USLT: {
            encoding: 1,
            language: 1,
            description: 'string',
            value: 'string'
        },
        
        COMM: {
            encoding: 1,
            language: 1,
            description: 'string',
            value: 'string'
        },
        
        APIC: {
            encoding: 1,
            mime: 'latin1',
            type: 'int8',
            description: 'string',
            data: 'binary'
        },
        
        UFID: {
            owner: 'latin1',
            identifier: 'binary'
        },

        MCDI: {
            value: 'binary'
        },
        
        PRIV: {
            owner: 'latin1',
            value: 'binary'
        },
        
        GEOB: {
            encoding: 1,
            mime: 'latin1',
            filename: 'string',
            description: 'string',
            data: 'binary'
        },
        
        PCNT: {
            value: 'int32+'
        },
        
        POPM: {
            email: 'latin1',
            rating: 'int8',
            counter: 'int32+'
        },
        
        AENC: {
            owner: 'latin1',
            previewStart: 'int16',
            previewLength: 'int16',
            encryptionInfo: 'binary'
        },
        
        ETCO: {
            format: 'int8',
            data: 'binary'  // TODO
        },
        
        MLLT: {
            framesBetweenReference: 'int16',
            bytesBetweenReference: 'int24',
            millisecondsBetweenReference: 'int24',
            bitsForBytesDeviation: 'int8',
            bitsForMillisecondsDev: 'int8',
            data: 'binary' // TODO
        },
        
        SYTC: {
            format: 'int8',
            tempoData: 'binary' // TODO
        },
        
        SYLT: {
            encoding: 1,
            language: 1,
            format: 'int8',
            contentType: 'int8',
            description: 'string',
            data: 'binary' // TODO
        },
        
        RVA2: {
            identification: 'latin1',
            data: 'binary' // TODO
        },
        
        EQU2: {
            interpolationMethod: 'int8',
            identification: 'latin1',
            data: 'binary' // TODO
        },
        
        RVRB: {
            left: 'int16',
            right: 'int16',
            bouncesLeft: 'int8',
            bouncesRight: 'int8',
            feedbackLL: 'int8',
            feedbackLR: 'int8',
            feedbackRR: 'int8',
            feedbackRL: 'int8',
            premixLR: 'int8',
            premixRL: 'int8'
        },
        
        RBUF: {
            size: 'int24',
            flag: 'int8',
            offset: 'int32'
        },
        
        LINK: {
            identifier: 'frame_id',
            url: 'latin1',
            data: 'binary' // TODO stringlist?
        },
        
        POSS: {
            format: 'int8',
            position: 'binary' // TODO
        },
        
        USER: {
            encoding: 1,
            language: 1,
            value: 'string'
        },
        
        OWNE: {
            encoding: 1,
            price: 'latin1',
            purchaseDate: 'date',
            seller: 'string'
        },
        
        COMR: {
            encoding: 1,
            price: 'latin1',
            validUntil: 'date',
            contactURL: 'latin1',
            receivedAs: 'int8',
            seller: 'string',
            description: 'string',
            logoMime: 'latin1',
            logo: 'binary'
        },
        
        ENCR: {
            owner: 'latin1',
            methodSymbol: 'int8',
            data: 'binary'
        },
        
        GRID: {
            owner: 'latin1',
            groupSymbol: 'int8',
            data: 'binary'
        },
        
        SIGN: {
            groupSymbol: 'int8',
            signature: 'binary'
        },
        
        SEEK: {
            value: 'int32'
        },
        
        ASPI: {
            dataStart: 'int32',
            dataLength: 'int32',
            numPoints: 'int16',
            bitsPerPoint: 'int8',
            data: 'binary' // TODO
        },
        
        // Deprecated ID3 v2.3 frames
        IPLS: {
            encoding: 1,
            value: 'string' // list?
        },
        
        RVAD: {
            adjustment: 'int8',
            bits: 'int8',
            data: 'binary' // TODO
        },
        
        EQUA: {
            adjustmentBits: 'int8',
            data: 'binary' // TODO
        }
    },
    
    names: {
        // Identification Frames
        'TIT1': 'grouping',
        'TIT2': 'title',
        'TIT3': 'subtitle',
        'TALB': 'album',
        'TOAL': 'originalAlbumTitle',
        'TRCK': 'trackNumber',
        'TPOS': 'diskNumber',
        'TSST': 'setSubtitle',
        'TSRC': 'ISRC',

        // Involved Persons Frames
        'TPE1': 'artist',
        'TPE2': 'albumArtist',
        'TPE3': 'conductor',
        'TPE4': 'modifiedBy',
        'TOPE': 'originalArtist',
        'TEXT': 'lyricist',
        'TOLY': 'originalLyricist',
        'TCOM': 'composer',
        'TMCL': 'musicianCreditsList',
        'TIPL': 'involvedPeopleList',
        'TENC': 'encodedBy',

        // Derived and Subjective Properties Frames
        'TBPM': 'tempo',
        'TLEN': 'length',
        'TKEY': 'initialKey',
        'TLAN': 'language',
        'TCON': 'genre',
        'TFLT': 'fileType',
        'TMED': 'mediaType',
        'TMOO': 'mood',

        // Rights and Licence Frames
        'TCOP': 'copyright',
        'TPRO': 'producedNotice',
        'TPUB': 'publisher',
        'TOWN': 'fileOwner',
        'TRSN': 'internetRadioStationName',
        'TRSO': 'internetRadioStationOwner',

        // Other Text Frames
        'TOFN': 'originalFilename',
        'TDLY': 'playlistDelay',
        'TDEN': 'encodingTime',
        'TDOR': 'originalReleaseTime',
        'TDRC': 'recordingTime',
        'TDRL': 'releaseTime',
        'TDTG': 'taggingTime',
        'TSSE': 'encodedWith',
        'TSOA': 'albumSortOrder',
        'TSOP': 'performerSortOrder',
        'TSOT': 'titleSortOrder',
        
        // User defined text information
        'TXXX': 'userText',
        
        // Unsynchronised lyrics/text transcription
        'USLT': 'lyrics',

        // Attached Picture Frame
        'APIC': 'coverArt',

        // Unique Identifier Frame
        'UFID': 'uniqueIdentifier',

        // Music CD Identifier Frame
        'MCDI': 'CDIdentifier',

        // Comment Frame
        'COMM': 'comments',
        
        // URL link frames
        'WCOM': 'commercialInformation',
        'WCOP': 'copyrightInformation',
        'WOAF': 'officialAudioFileWebpage',
        'WOAR': 'officialArtistWebpage',
        'WOAS': 'officialAudioSourceWebpage',
        'WORS': 'officialInternetRadioStationHomepage',
        'WPAY': 'payment',
        'WPUB': 'officialPublisherWebpage',

        // User Defined URL Link Frame
        'WXXX': 'url',

        'PRIV': 'private',
        'GEOB': 'generalEncapsulatedObject',
        'PCNT': 'playCount',
        'POPM': 'rating',
        'AENC': 'audioEncryption',
        'ETCO': 'eventTimingCodes',
        'MLLT': 'MPEGLocationLookupTable',
        'SYTC': 'synchronisedTempoCodes',
        'SYLT': 'synchronisedLyrics',
        'RVA2': 'volumeAdjustment',
        'EQU2': 'equalization',
        'RVRB': 'reverb',
        'RBUF': 'recommendedBufferSize',
        'LINK': 'link',
        'POSS': 'positionSynchronisation',
        'USER': 'termsOfUse',
        'OWNE': 'ownership',
        'COMR': 'commercial',
        'ENCR': 'encryption',
        'GRID': 'groupIdentifier',
        'SIGN': 'signature',
        'SEEK': 'seek',
        'ASPI': 'audioSeekPointIndex',

        // Deprecated ID3 v2.3 frames
        'TDAT': 'date',
        'TIME': 'time',
        'TORY': 'originalReleaseYear',
        'TRDA': 'recordingDates',
        'TSIZ': 'size',
        'TYER': 'year',
        'IPLS': 'involvedPeopleList',
        'RVAD': 'volumeAdjustment',
        'EQUA': 'equalization',
        
        // Non-standard iTunes frames
        'TCMP': 'compilation',
        'TSO2': 'albumArtistSortOrder',
        'TSOC': 'composerSortOrder'
    }
});

// ID3 v2.2 support
exports.ID3v22Stream = exports.ID3v23Stream.extend({    
    readHeader: function() {
        var id = this.stream.readString(3);
        
        if (this.frameReplacements[id] && !this.frameTypes[id])
            this.frameTypes[id] = this.frameReplacements[id];
        
        return {
            identifier: this.replacements[id] || id,
            length: this.stream.readUInt24()
        };
    },
    
    // map 3 char ID3 v2.2 names to 4 char ID3 v2.3/4 names
    replacements: {
        'UFI': 'UFID',
        'TT1': 'TIT1',
        'TT2': 'TIT2',
        'TT3': 'TIT3',
        'TP1': 'TPE1',
        'TP2': 'TPE2',
        'TP3': 'TPE3',
        'TP4': 'TPE4',
        'TCM': 'TCOM',
        'TXT': 'TEXT',
        'TLA': 'TLAN',
        'TCO': 'TCON',
        'TAL': 'TALB',
        'TPA': 'TPOS',
        'TRK': 'TRCK',
        'TRC': 'TSRC',
        'TYE': 'TYER',
        'TDA': 'TDAT',
        'TIM': 'TIME',
        'TRD': 'TRDA',
        'TMT': 'TMED',
        'TFT': 'TFLT',
        'TBP': 'TBPM',
        'TCR': 'TCOP',
        'TPB': 'TPUB',
        'TEN': 'TENC',
        'TSS': 'TSSE',
        'TOF': 'TOFN',
        'TLE': 'TLEN',
        'TSI': 'TSIZ',
        'TDY': 'TDLY',
        'TKE': 'TKEY',
        'TOT': 'TOAL',
        'TOA': 'TOPE',
        'TOL': 'TOLY',
        'TOR': 'TORY',
        'TXX': 'TXXX',
        
        'WAF': 'WOAF',
        'WAR': 'WOAR',
        'WAS': 'WOAS',
        'WCM': 'WCOM',
        'WCP': 'WCOP',
        'WPB': 'WPUB',
        'WXX': 'WXXX',
        
        'IPL': 'IPLS',
        'MCI': 'MCDI',
        'ETC': 'ETCO',
        'MLL': 'MLLT',
        'STC': 'SYTC',
        'ULT': 'USLT',
        'SLT': 'SYLT',
        'COM': 'COMM',
        'RVA': 'RVAD',
        'EQU': 'EQUA',
        'REV': 'RVRB',
        
        'GEO': 'GEOB',
        'CNT': 'PCNT',
        'POP': 'POPM',
        'BUF': 'RBUF',
        'CRA': 'AENC',
        'LNK': 'LINK',
        
        // iTunes stuff
        'TST': 'TSOT',
        'TSP': 'TSOP',
        'TSA': 'TSOA',
        'TCP': 'TCMP',
        'TS2': 'TSO2',
        'TSC': 'TSOC'
    },
    
    // replacements for ID3 v2.3/4 frames
    frameReplacements: {
        PIC: {
            encoding: 1,
            format: 'int24',
            type: 'int8',
            description: 'string',
            data: 'binary'
        },
        
        CRM: {
            owner: 'latin1',
            description: 'latin1',
            data: 'binary'
        }
    }
});
},{}],8:[function(require,module,exports){
function IMDCT() {
    this.tmp_imdct36 = new Float64Array(18);
    this.tmp_dctIV = new Float64Array(18);
    this.tmp_sdctII = new Float64Array(9);
}

// perform X[18]->x[36] IMDCT using Szu-Wei Lee's fast algorithm
IMDCT.prototype.imdct36 = function(x, y) {
    var tmp = this.tmp_imdct36;

    /* DCT-IV */
    this.dctIV(x, tmp);

    // convert 18-point DCT-IV to 36-point IMDCT
    for (var i =  0; i <  9; ++i) {
        y[i] =  tmp[9 + i];
    }
    for (var i =  9; i < 27; ++i) {
        y[i] = -tmp[36 - (9 + i) - 1];
    }
    for (var i = 27; i < 36; ++i) {
        y[i] = -tmp[i - 27];
    }
};

var dctIV_scale = [];
for(i = 0; i < 18; i++) {
    dctIV_scale[i] = 2 * Math.cos(Math.PI * (2 * i + 1) / (4 * 18));
}

IMDCT.prototype.dctIV = function(y, X) {
    var tmp = this.tmp_dctIV;

    // scaling
    for (var i = 0; i < 18; ++i) {
        tmp[i] = y[i] * dctIV_scale[i];
    }

    // SDCT-II
    this.sdctII(tmp, X);

    // scale reduction and output accumulation
    X[0] /= 2;
    for (var i = 1; i < 18; ++i) {
        X[i] = X[i] / 2 - X[i - 1];
    }
};

var sdctII_scale = [];
for (var i = 0; i < 9; ++i) {
    sdctII_scale[i] = 2 * Math.cos(Math.PI * (2 * i + 1) / (2 * 18));
}

IMDCT.prototype.sdctII = function(x, X) {
    // divide the 18-point SDCT-II into two 9-point SDCT-IIs
    var tmp = this.tmp_sdctII;

    // even input butterfly
    for (var i = 0; i < 9; ++i) {
        tmp[i] = x[i] + x[18 - i - 1];
    }

    fastsdct(tmp, X, 0);

    // odd input butterfly and scaling
    for (var i = 0; i < 9; ++i) {
        tmp[i] = (x[i] - x[18 - i - 1]) * sdctII_scale[i];
    }

    fastsdct(tmp, X, 1);

    // output accumulation
    for (var i = 3; i < 18; i += 2) {
        X[i] -= X[i - 2];
    }
};

var c0 = 2 * Math.cos( 1 * Math.PI / 18);
var c1 = 2 * Math.cos( 3 * Math.PI / 18);
var c2 = 2 * Math.cos( 4 * Math.PI / 18);
var c3 = 2 * Math.cos( 5 * Math.PI / 18);
var c4 = 2 * Math.cos( 7 * Math.PI / 18);
var c5 = 2 * Math.cos( 8 * Math.PI / 18);
var c6 = 2 * Math.cos(16 * Math.PI / 18);

function fastsdct(x, y, offset) {
    var a0,  a1,  a2,  a3,  a4,  a5,  a6,  a7,  a8,  a9,  a10, a11, a12;
    var a13, a14, a15, a16, a17, a18, a19, a20, a21, a22, a23, a24, a25;
    var m0,  m1,  m2,  m3,  m4,  m5,  m6,  m7;

    a0 = x[3] + x[5];
    a1 = x[3] - x[5];
    a2 = x[6] + x[2];
    a3 = x[6] - x[2];
    a4 = x[1] + x[7];
    a5 = x[1] - x[7];
    a6 = x[8] + x[0];
    a7 = x[8] - x[0];

    a8  = a0  + a2;
    a9  = a0  - a2;
    a10 = a0  - a6;
    a11 = a2  - a6;
    a12 = a8  + a6;
    a13 = a1  - a3;
    a14 = a13 + a7;
    a15 = a3  + a7;
    a16 = a1  - a7;
    a17 = a1  + a3;

    m0 = a17 * -c3;
    m1 = a16 * -c0;
    m2 = a15 * -c4;
    m3 = a14 * -c1;
    m4 = a5  * -c1;
    m5 = a11 * -c6;
    m6 = a10 * -c5;
    m7 = a9  * -c2;

    a18 =     x[4] + a4;
    a19 = 2 * x[4] - a4;
    a20 = a19 + m5;
    a21 = a19 - m5;
    a22 = a19 + m6;
    a23 = m4  + m2;
    a24 = m4  - m2;
    a25 = m4  + m1;

    // output to every other slot for convenience
    y[offset +  0] = a18 + a12;
    y[offset +  2] = m0  - a25;
    y[offset +  4] = m7  - a20;
    y[offset +  6] = m3;
    y[offset +  8] = a21 - m6;
    y[offset + 10] = a24 - m1;
    y[offset + 12] = a12 - 2 * a18;
    y[offset + 14] = a23 + m0;
    y[offset + 16] = a22 + m7;
}

IMDCT.S = [
  /*  0 */  [ 0.608761429,
              -0.923879533,
              -0.130526192,
               0.991444861,
              -0.382683432,
              -0.793353340 ],

  /*  6 */  [ -0.793353340,
               0.382683432,
               0.991444861,
               0.130526192,
              -0.923879533,
              -0.608761429 ],

  /*  1 */  [  0.382683432,
              -0.923879533,
               0.923879533,
              -0.382683432,
              -0.382683432,
               0.923879533 ],

  /*  7 */  [ -0.923879533,
              -0.382683432,
               0.382683432,
               0.923879533,
               0.923879533,
               0.382683432 ],

  /*  2 */  [  0.130526192,
              -0.382683432,
               0.608761429,
              -0.793353340,
               0.923879533,
              -0.991444861 ],

  /*  8 */  [ -0.991444861,
              -0.923879533,
              -0.793353340,
              -0.608761429,
              -0.382683432,
              -0.130526192 ]
];

module.exports = IMDCT;

},{}],9:[function(require,module,exports){
var tables = require('./tables');
var MP3FrameHeader = require('./header');
var MP3Frame = require('./frame');
var utils = require('./utils');

function Layer1() {    
    this.allocation = utils.makeArray([2, 32], Uint8Array);
    this.scalefactor = utils.makeArray([2, 32], Uint8Array);
}

MP3Frame.layers[1] = Layer1;

// linear scaling table
const LINEAR_TABLE = new Float32Array([
    1.33333333333333, 1.14285714285714, 1.06666666666667,
    1.03225806451613, 1.01587301587302, 1.00787401574803,
    1.00392156862745, 1.00195694716243, 1.00097751710655,
    1.00048851978505, 1.00024420024420, 1.00012208521548,
    1.00006103888177, 1.00003051850948
]);

Layer1.prototype.decode = function(stream, frame) {
    var header = frame.header;
    var nch = header.nchannels();
    
    var bound = 32;
    if (header.mode === MP3FrameHeader.MODE.JOINT_STEREO) {
        header.flags |= MP3FrameHeader.FLAGS.I_STEREO;
        bound = 4 + header.mode_extension * 4;
    }
    
    if (header.flags & MP3FrameHeader.FLAGS.PROTECTION) {
        // TODO: crc check
    }
    
    // decode bit allocations
    var allocation = this.allocation;
    for (var sb = 0; sb < bound; sb++) {
        for (var ch = 0; ch < nch; ch++) {
            var nb = stream.read(4);
            if (nb === 15)
                throw new Error("forbidden bit allocation value");
                
            allocation[ch][sb] = nb ? nb + 1 : 0;
        }
    }
    
    for (var sb = bound; sb < 32; sb++) {
        var nb = stream.read(4);
        if (nb === 15)
            throw new Error("forbidden bit allocation value");
            
        allocation[0][sb] =
        allocation[1][sb] = nb ? nb + 1 : 0;
    }
    
    // decode scalefactors
    var scalefactor = this.scalefactor;
    for (var sb = 0; sb < 32; sb++) {
        for (var ch = 0; ch < nch; ch++) {
            if (allocation[ch][sb]) {
                scalefactor[ch][sb] = stream.read(6);
                
            	/*
            	 * Scalefactor index 63 does not appear in Table B.1 of
            	 * ISO/IEC 11172-3. Nonetheless, other implementations accept it,
                 * so we do as well 
                 */
            }
        }
    }
    
    // decode samples
    for (var s = 0; s < 12; s++) {
        for (var sb = 0; sb < bound; sb++) {
            for (var ch = 0; ch < nch; ch++) {
                var nb = allocation[ch][sb];
                frame.sbsample[ch][s][sb] = nb ? this.sample(stream, nb) * tables.SF_TABLE[scalefactor[ch][sb]] : 0;
            }
        }
        
        for (var sb = bound; sb < 32; sb++) {
            var nb = allocation[0][sb];
            if (nb) {
                var sample = this.sample(stream, nb);
                
                for (var ch = 0; ch < nch; ch++) {
                    frame.sbsample[ch][s][sb] = sample * tables.SF_TABLE[scalefactor[ch][sb]];
                }
            } else {
                for (var ch = 0; ch < nch; ch++) {
                    frame.sbsample[ch][s][sb] = 0;
                }
            }
        }
    }
};

Layer1.prototype.sample = function(stream, nb) {
    var sample = stream.read(nb);
    
    // invert most significant bit, and form a 2's complement sample
    sample ^= 1 << (nb - 1);
    sample |= -(sample & (1 << (nb - 1)));
    sample /= (1 << (nb - 1));
        
    // requantize the sample
    // s'' = (2^nb / (2^nb - 1)) * (s''' + 2^(-nb + 1))
    sample += 1 >> (nb - 1);
    return sample * LINEAR_TABLE[nb - 2];
};

module.exports = Layer1;

},{"./frame":4,"./header":5,"./tables":14,"./utils":15}],10:[function(require,module,exports){
var tables = require('./tables');
var MP3FrameHeader = require('./header');
var MP3Frame = require('./frame');
var utils = require('./utils');

function Layer2() {    
    this.samples = new Float64Array(3);
    this.allocation = utils.makeArray([2, 32], Uint8Array);
    this.scfsi = utils.makeArray([2, 32], Uint8Array);
    this.scalefactor = utils.makeArray([2, 32, 3], Uint8Array);
}

MP3Frame.layers[2] = Layer2;

// possible quantization per subband table
const SBQUANT = [
  // ISO/IEC 11172-3 Table B.2a
  { sblimit: 27, offsets:
      [ 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0, 0 ] },
      
  // ISO/IEC 11172-3 Table B.2b
  { sblimit: 30, offsets:
      [ 7, 7, 7, 6, 6, 6, 6, 6, 6, 6, 6, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 0, 0, 0, 0, 0, 0, 0 ] },
      
  // ISO/IEC 11172-3 Table B.2c
  {  sblimit: 8, offsets:
      [ 5, 5, 2, 2, 2, 2, 2, 2 ] },
      
  // ISO/IEC 11172-3 Table B.2d
  { sblimit: 12, offsets:
      [ 5, 5, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2 ] },
      
  // ISO/IEC 13818-3 Table B.1
  { sblimit: 30, offsets:
      [ 4, 4, 4, 4, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1 ] }
];

// bit allocation table
const BITALLOC = [
    { nbal: 2, offset: 0 },  // 0
    { nbal: 2, offset: 3 },  // 1
    { nbal: 3, offset: 3 },  // 2
    { nbal: 3, offset: 1 },  // 3
    { nbal: 4, offset: 2 },  // 4
    { nbal: 4, offset: 3 },  // 5
    { nbal: 4, offset: 4 },  // 6
    { nbal: 4, offset: 5 }   // 7
];

// offsets into quantization class table
const OFFSETS = [
    [ 0, 1, 16                                             ],  // 0
    [ 0, 1,  2, 3, 4, 5, 16                                ],  // 1
    [ 0, 1,  2, 3, 4, 5,  6, 7,  8,  9, 10, 11, 12, 13, 14 ],  // 2
    [ 0, 1,  3, 4, 5, 6,  7, 8,  9, 10, 11, 12, 13, 14, 15 ],  // 3
    [ 0, 1,  2, 3, 4, 5,  6, 7,  8,  9, 10, 11, 12, 13, 16 ],  // 4
    [ 0, 2,  4, 5, 6, 7,  8, 9, 10, 11, 12, 13, 14, 15, 16 ]   // 5
];



/*
 * These are the Layer II classes of quantization.
 * The table is derived from Table B.4 of ISO/IEC 11172-3.
 */
const QC_TABLE = [
    { nlevels:     3, group: 2, bits:  5, C: 1.33333333333, D: 0.50000000000 },
    { nlevels:     5, group: 3, bits:  7, C: 1.60000000000, D: 0.50000000000 },
    { nlevels:     7, group: 0, bits:  3, C: 1.14285714286, D: 0.25000000000 },
    { nlevels:     9, group: 4, bits: 10, C: 1.77777777777, D: 0.50000000000 },
    { nlevels:    15, group: 0, bits:  4, C: 1.06666666666, D: 0.12500000000 },
    { nlevels:    31, group: 0, bits:  5, C: 1.03225806452, D: 0.06250000000 },
    { nlevels:    63, group: 0, bits:  6, C: 1.01587301587, D: 0.03125000000 },
    { nlevels:   127, group: 0, bits:  7, C: 1.00787401575, D: 0.01562500000 },
    { nlevels:   255, group: 0, bits:  8, C: 1.00392156863, D: 0.00781250000 },
    { nlevels:   511, group: 0, bits:  9, C: 1.00195694716, D: 0.00390625000 },
    { nlevels:  1023, group: 0, bits: 10, C: 1.00097751711, D: 0.00195312500 },
    { nlevels:  2047, group: 0, bits: 11, C: 1.00048851979, D: 0.00097656250 },
    { nlevels:  4095, group: 0, bits: 12, C: 1.00024420024, D: 0.00048828125 },
    { nlevels:  8191, group: 0, bits: 13, C: 1.00012208522, D: 0.00024414063 },
    { nlevels: 16383, group: 0, bits: 14, C: 1.00006103888, D: 0.00012207031 },
    { nlevels: 32767, group: 0, bits: 15, C: 1.00003051851, D: 0.00006103516 },
    { nlevels: 65535, group: 0, bits: 16, C: 1.00001525902, D: 0.00003051758 }
];

Layer2.prototype.decode = function(stream, frame) {
    var header = frame.header;
    var nch = header.nchannels();
    var index;
    
    if (header.flags & MP3FrameHeader.FLAGS.LSF_EXT) {
        index = 4;
    } else if (header.flags & MP3FrameHeader.FLAGS.FREEFORMAT) {
        index = header.samplerate === 48000 ? 0 : 1;
    } else {
        var bitrate_per_channel = header.bitrate;
        
        if (nch === 2) {
            bitrate_per_channel /= 2;
            
            /*
             * ISO/IEC 11172-3 allows only single channel mode for 32, 48, 56, and
             * 80 kbps bitrates in Layer II, but some encoders ignore this
             * restriction, so we ignore it as well.
             */
        } else {
            /*
        	 * ISO/IEC 11172-3 does not allow single channel mode for 224, 256,
        	 * 320, or 384 kbps bitrates in Layer II.
        	 */
            if (bitrate_per_channel > 192000)
                throw new Error('bad bitrate/mode combination');
        }
        
        if (bitrate_per_channel <= 48000)
            index = header.samplerate === 32000 ? 3 : 2;
        else if (bitrate_per_channel <= 80000)
            index = 0;
        else
            index = header.samplerate === 48000 ? 0 : 1;
    }
    
    var sblimit = SBQUANT[index].sblimit;
    var offsets = SBQUANT[index].offsets;
    
    var bound = 32;
    if (header.mode === MP3FrameHeader.MODE.JOINT_STEREO) {
        header.flags |= MP3FrameHeader.FLAGS.I_STEREO;
        bound = 4 + header.mode_extension * 4;
    }
    
    if (bound > sblimit)
        bound = sblimit;
    
    // decode bit allocations
    var allocation = this.allocation;
    for (var sb = 0; sb < bound; sb++) {
        var nbal = BITALLOC[offsets[sb]].nbal;
        
        for (var ch = 0; ch < nch; ch++)
            allocation[ch][sb] = stream.read(nbal);
    }
    
    for (var sb = bound; sb < sblimit; sb++) {
        var nbal = BITALLOC[offsets[sb]].nbal;
        
        allocation[0][sb] =
        allocation[1][sb] = stream.read(nbal);
    }
    
    // decode scalefactor selection info
    var scfsi = this.scfsi;
    for (var sb = 0; sb < sblimit; sb++) {
        for (var ch = 0; ch < nch; ch++) {
            if (allocation[ch][sb])
                scfsi[ch][sb] = stream.read(2);
        }
    }
    
    if (header.flags & MP3FrameHeader.FLAGS.PROTECTION) {
        // TODO: crc check
    }
    
    // decode scalefactors
    var scalefactor = this.scalefactor;
    for (var sb = 0; sb < sblimit; sb++) {
        for (var ch = 0; ch < nch; ch++) {
            if (allocation[ch][sb]) {
                scalefactor[ch][sb][0] = stream.read(6);
                
                switch (scfsi[ch][sb]) {
            	    case 2:
            	        scalefactor[ch][sb][2] =
                        scalefactor[ch][sb][1] = scalefactor[ch][sb][0];
                        break;
                        
                    case 0:
                        scalefactor[ch][sb][1] = stream.read(6);
                    	// fall through
                    	
                    case 1:
                    case 3:
                        scalefactor[ch][sb][2] = stream.read(6);
                }
                
                if (scfsi[ch][sb] & 1)
                    scalefactor[ch][sb][1] = scalefactor[ch][sb][scfsi[ch][sb] - 1];
                    
                /*
            	 * Scalefactor index 63 does not appear in Table B.1 of
            	 * ISO/IEC 11172-3. Nonetheless, other implementations accept it,
            	 * so we do as well.
            	 */
            }
        }
    }
    
    // decode samples
    for (var gr = 0; gr < 12; gr++) {
        // normal
        for (var sb = 0; sb < bound; sb++) {
            for (var ch = 0; ch < nch; ch++) {                
                if (index = allocation[ch][sb]) {
                    index = OFFSETS[BITALLOC[offsets[sb]].offset][index - 1];
                    this.decodeSamples(stream, QC_TABLE[index]);
                    
                    var scale = tables.SF_TABLE[scalefactor[ch][sb][gr >> 2]];
                    for (var s = 0; s < 3; s++) {
                        frame.sbsample[ch][3 * gr + s][sb] = this.samples[s] * scale;
                    }
                } else {
                    for (var s = 0; s < 3; s++) {
                        frame.sbsample[ch][3 * gr + s][sb] = 0;
                    }
                }
            }
        }
        
        // joint stereo
        for (var sb = bound; sb < sblimit; sb++) {
            if (index = allocation[0][sb]) {
                index = OFFSETS[BITALLOC[offsets[sb]].offset][index - 1];
                this.decodeSamples(stream, QC_TABLE[index]);
                
                for (var ch = 0; ch < nch; ch++) {
                    var scale = tables.SF_TABLE[scalefactor[ch][sb][gr >> 2]];
                    for (var s = 0; s < 3; s++) {
                        frame.sbsample[ch][3 * gr + s][sb] = this.samples[s] * scale;
                    }
                }
            } else {
                for (var ch = 0; ch < nch; ch++) {
                    for (var s = 0; s < 3; s++) {
                        frame.sbsample[ch][3 * gr + s][sb] = 0;
                    }
                }
            }
        }
        
        // the rest
        for (var ch = 0; ch < nch; ch++) {
            for (var s = 0; s < 3; s++) {
                for (var sb = sblimit; sb < 32; sb++) {
                    frame.sbsample[ch][3 * gr + s][sb] = 0;
                }
            }
        }
    }
};

Layer2.prototype.decodeSamples = function(stream, quantclass) {
    var sample = this.samples;
    var nb = quantclass.group;
    
    if (nb) {
        // degrouping
        var c = stream.read(quantclass.bits);
        var nlevels = quantclass.nlevels;
        
        for (var s = 0; s < 3; s++) {
            sample[s] = c % nlevels;
            c = c / nlevels | 0;
        }
    } else {
        nb = quantclass.bits;
        for (var s = 0; s < 3; s++) {
            sample[s] = stream.read(nb);
        }
    }
    
    for (var s = 0; s < 3; s++) {
        // invert most significant bit, and form a 2's complement sample
        var requantized = sample[s] ^ (1 << (nb - 1));
        requantized |= -(requantized & (1 << (nb - 1)));
        requantized /= (1 << (nb - 1));
        
        // requantize the sample
        sample[s] = (requantized + quantclass.D) * quantclass.C;
    }
};

module.exports = Layer2;

},{"./frame":4,"./header":5,"./tables":14,"./utils":15}],11:[function(require,module,exports){
var AV = (window.AV);
var tables = require('./tables');
var MP3FrameHeader = require('./header');
var MP3Frame = require('./frame');
var huffman = require('./huffman');
var IMDCT = require('./imdct');
var utils = require('./utils');

function MP3SideInfo() {
    this.main_data_begin = null;
    this.private_bits = null;
    this.gr = [new MP3Granule(), new MP3Granule()];
    this.scfsi = new Uint8Array(2);
}

function MP3Granule() {
    this.ch = [new MP3Channel(), new MP3Channel()];
}

function MP3Channel() {
    // from side info
    this.part2_3_length    = null;
    this.big_values        = null;
    this.global_gain       = null;
    this.scalefac_compress = null;
    
    this.flags         = null;
    this.block_type    = null;
    this.table_select  = new Uint8Array(3);
    this.subblock_gain = new Uint8Array(3);
    this.region0_count = null;
    this.region1_count = null;
    
    // from main_data
    this.scalefac = new Uint8Array(39);
}

function Layer3() {
    this.imdct = new IMDCT();
    this.si = new MP3SideInfo();
    
    // preallocate reusable typed arrays for performance
    this.xr = [new Float64Array(576), new Float64Array(576)];
    this._exponents = new Int32Array(39);
    this.reqcache = new Float64Array(16);
    this.modes = new Int16Array(39);
    this.output = new Float64Array(36);
    
    this.tmp = utils.makeArray([32, 3, 6]);
    this.tmp2 = new Float64Array(32 * 3 * 6);
}

MP3Frame.layers[3] = Layer3;

Layer3.prototype.decode = function(stream, frame) {
    var header = frame.header;
    var next_md_begin = 0;
    var md_len = 0;
    
    var nch = header.nchannels();
    var si_len = (header.flags & MP3FrameHeader.FLAGS.LSF_EXT) ? (nch === 1 ? 9 : 17) : (nch === 1 ? 17 : 32);
        
    // check frame sanity
    if (stream.next_frame - stream.nextByte() < si_len) {
        stream.md_len = 0;
        throw new Error('Bad frame length');
    }
    
    // check CRC word
    if (header.flags & MP3FrameHeader.FLAGS.PROTECTION) {
        // TODO: crc check
    }
    
    // decode frame side information
    var sideInfo = this.sideInfo(stream, nch, header.flags & MP3FrameHeader.FLAGS.LSF_EXT);        
    var si = sideInfo.si;
    var data_bitlen = sideInfo.data_bitlen;
    var priv_bitlen = sideInfo.priv_bitlen;
    
    header.flags        |= priv_bitlen;
    header.private_bits |= si.private_bits;
    
    // find main_data of next frame
    var peek = stream.copy();
    peek.seek(stream.next_frame * 8);
    
    var nextHeader = peek.read(16);    
    if ((nextHeader & 0xffe6) === 0xffe2) { // syncword | layer
        if ((nextHeader & 1) === 0) // protection bit
            peek.advance(16); // crc check
            
        peek.advance(16); // skip the rest of the header
        next_md_begin = peek.read((nextHeader & 8) ? 9 : 8);
    }
    
    // find main_data of this frame
    var frame_space = stream.next_frame - stream.nextByte();
    
    if (next_md_begin > si.main_data_begin + frame_space)
        next_md_begin = 0;
        
    var md_len = si.main_data_begin + frame_space - next_md_begin;
    var frame_used = 0;
    var ptr;
    
    if (si.main_data_begin === 0) {
        ptr = stream.stream;
        stream.md_len = 0;
        frame_used = md_len;
    } else {
        if (si.main_data_begin > stream.md_len) {
            throw new Error('bad main_data_begin pointer');
        } else {
            var old_md_len = stream.md_len;
            
            if (md_len > si.main_data_begin) {
                if (stream.md_len + md_len - si.main_data_begin > MP3FrameHeader.BUFFER_MDLEN) {
                    throw new Error("Assertion failed: (stream.md_len + md_len - si.main_data_begin <= MAD_MP3FrameHeader.BUFFER_MDLEN)");
                }
                
                frame_used = md_len - si.main_data_begin;
                this.memcpy(stream.main_data, stream.md_len, stream.stream.stream, stream.nextByte(), frame_used);
                stream.md_len += frame_used;
            }
            
            ptr = new AV.Bitstream(AV.Stream.fromBuffer(new AV.Buffer(stream.main_data)));
            ptr.advance((old_md_len - si.main_data_begin) * 8);
        }
    }
    
    var frame_free = frame_space - frame_used;
    
    // decode main_data
    this.decodeMainData(ptr, frame, si, nch);
    
    // preload main_data buffer with up to 511 bytes for next frame(s)
    if (frame_free >= next_md_begin) {
        this.memcpy(stream.main_data, 0, stream.stream.stream, stream.next_frame - next_md_begin, next_md_begin);
        stream.md_len = next_md_begin;
    } else {
        if (md_len < si.main_data_begin) {
            var extra = si.main_data_begin - md_len;
            if (extra + frame_free > next_md_begin)
                extra = next_md_begin - frame_free;

            if (extra < stream.md_len) {
                this.memcpy(stream.main_data, 0, stream.main_data, stream.md_len - extra, extra);
                stream.md_len = extra;
            }
        } else {
            stream.md_len = 0;
        }
        
        this.memcpy(stream.main_data, stream.md_len, stream.stream.stream, stream.next_frame - frame_free, frame_free);
        stream.md_len += frame_free;
    }
};

Layer3.prototype.memcpy = function(dst, dstOffset, pSrc, srcOffset, length) {
    var subarr;
    if (pSrc.subarray)
        subarr = pSrc.subarray(srcOffset, srcOffset + length);
    else
        subarr = pSrc.peekBuffer(srcOffset - pSrc.offset, length).data;

    // oh my, memcpy actually exists in JavaScript?
    dst.set(subarr, dstOffset);
    return dst;
};

Layer3.prototype.sideInfo = function(stream, nch, lsf) {
    var si = this.si;
    var data_bitlen = 0;
    var priv_bitlen = lsf ? ((nch === 1) ? 1 : 2) : ((nch === 1) ? 5 : 3);
    
    si.main_data_begin = stream.read(lsf ? 8 : 9);
    si.private_bits    = stream.read(priv_bitlen);

    var ngr = 1;
    if (!lsf) {
        ngr = 2;
        for (var ch = 0; ch < nch; ++ch)
            si.scfsi[ch] = stream.read(4);
    }
    
    for (var gr = 0; gr < ngr; gr++) {
        var granule = si.gr[gr];
        
        for (var ch = 0; ch < nch; ch++) {
            var channel = granule.ch[ch];
            
            channel.part2_3_length    = stream.read(12);
            channel.big_values        = stream.read(9);
            channel.global_gain       = stream.read(8);
            channel.scalefac_compress = stream.read(lsf ? 9 : 4);

            data_bitlen += channel.part2_3_length;

            if (channel.big_values > 288)
                throw new Error('bad big_values count');

            channel.flags = 0;

            // window_switching_flag
            if (stream.read(1)) {
                channel.block_type = stream.read(2);

                if (channel.block_type === 0)
                    throw new Error('reserved block_type');

                if (!lsf && channel.block_type === 2 && si.scfsi[ch])
                    throw new Error('bad scalefactor selection info');

                channel.region0_count = 7;
                channel.region1_count = 36;

                if (stream.read(1))
                    channel.flags |= tables.MIXED_BLOCK_FLAG;
                else if (channel.block_type === 2)
                    channel.region0_count = 8;

                for (var i = 0; i < 2; i++)
                    channel.table_select[i] = stream.read(5);

                for (var i = 0; i < 3; i++)
                    channel.subblock_gain[i] = stream.read(3);
            } else {
                channel.block_type = 0;

                for (var i = 0; i < 3; i++)
                    channel.table_select[i] = stream.read(5);

                channel.region0_count = stream.read(4);
                channel.region1_count = stream.read(3);
            }

            // [preflag,] scalefac_scale, count1table_select
            channel.flags |= stream.read(lsf ? 2 : 3);
        }
    }
    
    return {
        si: si,
        data_bitlen: data_bitlen,
        priv_bitlen: priv_bitlen
    };
};

Layer3.prototype.decodeMainData = function(stream, frame, si, nch) {
    var header = frame.header;
    var sfreq = header.samplerate;

    if (header.flags & MP3FrameHeader.FLAGS.MPEG_2_5_EXT)
        sfreq *= 2;

    // 48000 => 0, 44100 => 1, 32000 => 2,
    // 24000 => 3, 22050 => 4, 16000 => 5
    var sfreqi = ((sfreq >>  7) & 0x000f) + ((sfreq >> 15) & 0x0001) - 8;

    if (header.flags & MP3FrameHeader.FLAGS.MPEG_2_5_EXT)
        sfreqi += 3;
        
    // scalefactors, Huffman decoding, requantization
    var ngr = (header.flags & MP3FrameHeader.FLAGS.LSF_EXT) ? 1 : 2;
    var xr = this.xr;
    
    for (var gr = 0; gr < ngr; ++gr) {
        var granule = si.gr[gr];
        var sfbwidth = [];
        var l = 0;
        
        for (var ch = 0; ch < nch; ++ch) {
            var channel = granule.ch[ch];
            var part2_length;
            
            sfbwidth[ch] = tables.SFBWIDTH_TABLE[sfreqi].l;
            if (channel.block_type === 2) {
                sfbwidth[ch] = (channel.flags & tables.MIXED_BLOCK_FLAG) ? tables.SFBWIDTH_TABLE[sfreqi].m : tables.SFBWIDTH_TABLE[sfreqi].s;
            }

            if (header.flags & MP3FrameHeader.FLAGS.LSF_EXT) {
                part2_length = this.scalefactors_lsf(stream, channel, ch === 0 ? 0 : si.gr[1].ch[1], header.mode_extension);
            } else {
                part2_length = this.scalefactors(stream, channel, si.gr[0].ch[ch], gr === 0 ? 0 : si.scfsi[ch]);
            }

            this.huffmanDecode(stream, xr[ch], channel, sfbwidth[ch], part2_length);
        }
        
        // joint stereo processing
        if (header.mode === MP3FrameHeader.MODE.JOINT_STEREO && header.mode_extension !== 0)
            this.stereo(xr, si.gr, gr, header, sfbwidth[0]);
        
        // reordering, alias reduction, IMDCT, overlap-add, frequency inversion
        for (var ch = 0; ch < nch; ch++) {
            var channel = granule.ch[ch];
            var sample = frame.sbsample[ch].slice(18 * gr);
            
            var sb, l = 0, i, sblimit;
            var output = this.output;
            
            if (channel.block_type === 2) {
                this.reorder(xr[ch], channel, sfbwidth[ch]);

                /*
                 * According to ISO/IEC 11172-3, "Alias reduction is not applied for
                 * granules with block_type === 2 (short block)." However, other
                 * sources suggest alias reduction should indeed be performed on the
                 * lower two subbands of mixed blocks. Most other implementations do
                 * this, so by default we will too.
                 */
                if (channel.flags & tables.MIXED_BLOCK_FLAG)
                    this.aliasreduce(xr[ch], 36);
            } else {
                this.aliasreduce(xr[ch], 576);
            }
            
            // subbands 0-1
            if (channel.block_type !== 2 || (channel.flags & tables.MIXED_BLOCK_FLAG)) {
                var block_type = channel.block_type;
                if (channel.flags & tables.MIXED_BLOCK_FLAG)
                    block_type = 0;

                // long blocks
                for (var sb = 0; sb < 2; ++sb, l += 18) {
                    this.imdct_l(xr[ch].subarray(l, l + 18), output, block_type);
                    this.overlap(output, frame.overlap[ch][sb], sample, sb);
                }
            } else {
                // short blocks
                for (var sb = 0; sb < 2; ++sb, l += 18) {
                    this.imdct_s(xr[ch].subarray(l, l + 18), output);
                    this.overlap(output, frame.overlap[ch][sb], sample, sb);
                }
            }
            
            this.freqinver(sample, 1);

            // (nonzero) subbands 2-31
            var i = 576;
            while (i > 36 && xr[ch][i - 1] === 0) {
                --i;
            }
            
            sblimit = 32 - (((576 - i) / 18) << 0);

            if (channel.block_type !== 2) {
                // long blocks
                for (var sb = 2; sb < sblimit; ++sb, l += 18) {
                    this.imdct_l(xr[ch].subarray(l, l + 18), output, channel.block_type);
                    this.overlap(output, frame.overlap[ch][sb], sample, sb);

                    if (sb & 1)
                        this.freqinver(sample, sb);
                }
            } else {
                // short blocks
                for (var sb = 2; sb < sblimit; ++sb, l += 18) {
                    this.imdct_s(xr[ch].subarray(l, l + 18), output);
                    this.overlap(output, frame.overlap[ch][sb], sample, sb);

                    if (sb & 1)
                        this.freqinver(sample, sb);
                }
            }
            
            // remaining (zero) subbands
            for (var sb = sblimit; sb < 32; ++sb) {
                this.overlap_z(frame.overlap[ch][sb], sample, sb);

                if (sb & 1)
                    this.freqinver(sample, sb);
            }
        }
    }
};

Layer3.prototype.scalefactors = function(stream, channel, gr0ch, scfsi) {
    var start = stream.offset();
    var slen1 = tables.SFLEN_TABLE[channel.scalefac_compress].slen1;
    var slen2 = tables.SFLEN_TABLE[channel.scalefac_compress].slen2;
    var sfbi;
    
    if (channel.block_type === 2) {
        sfbi = 0;

        var nsfb = (channel.flags & tables.MIXED_BLOCK_FLAG) ? 8 + 3 * 3 : 6 * 3;
        while (nsfb--)
            channel.scalefac[sfbi++] = stream.read(slen1);

        nsfb = 6 * 3;
        while (nsfb--)
            channel.scalefac[sfbi++] = stream.read(slen2);

        nsfb = 1 * 3;
        while (nsfb--)
            channel.scalefac[sfbi++] = 0;
    } else {
        if (scfsi & 0x8) {
            for (var sfbi = 0; sfbi < 6; ++sfbi)
                channel.scalefac[sfbi] = gr0ch.scalefac[sfbi];
        } else {
            for (var sfbi = 0; sfbi < 6; ++sfbi)
                channel.scalefac[sfbi] = stream.read(slen1);
        }

        if (scfsi & 0x4) {
            for (var sfbi = 6; sfbi < 11; ++sfbi)
                channel.scalefac[sfbi] = gr0ch.scalefac[sfbi];
        } else {
            for (var sfbi = 6; sfbi < 11; ++sfbi)
                channel.scalefac[sfbi] = stream.read(slen1);
        }

        if (scfsi & 0x2) {
            for (var sfbi = 11; sfbi < 16; ++sfbi)
                channel.scalefac[sfbi] = gr0ch.scalefac[sfbi];
        } else {
            for (var sfbi = 11; sfbi < 16; ++sfbi)
                channel.scalefac[sfbi] = stream.read(slen2);
        }

        if (scfsi & 0x1) {
            for (var sfbi = 16; sfbi < 21; ++sfbi)
                channel.scalefac[sfbi] = gr0ch.scalefac[sfbi];
        } else {
            for (var sfbi = 16; sfbi < 21; ++sfbi)
                channel.scalefac[sfbi] = stream.read(slen2);
        }

        channel.scalefac[21] = 0;
    }
    
    return stream.offset() - start;
};

Layer3.prototype.scalefactors_lsf = function(stream, channel, gr1ch, mode_extension) {
    var start = stream.offset();
    var scalefac_compress = channel.scalefac_compress;
    var index = channel.block_type === 2 ? (channel.flags & tables.MIXED_BLOCK_FLAG ? 2 : 1) : 0;
    var slen = new Int32Array(4);
    var nsfb;
    
    if (!((mode_extension & tables.I_STEREO) && gr1ch)) {
        if (scalefac_compress < 400) {
            slen[0] = (scalefac_compress >>> 4) / 5;
            slen[1] = (scalefac_compress >>> 4) % 5;
            slen[2] = (scalefac_compress % 16) >>> 2;
            slen[3] =  scalefac_compress %  4;
        
            nsfb = tables.NSFB_TABLE[0][index];
        } else if (scalefac_compress < 500) {
            scalefac_compress -= 400;

            slen[0] = (scalefac_compress >>> 2) / 5;
            slen[1] = (scalefac_compress >>> 2) % 5;
            slen[2] =  scalefac_compress % 4;
            slen[3] = 0;

            nsfb = tables.NSFB_TABLE[1][index];
        } else {
            scalefac_compress -= 500;

            slen[0] = scalefac_compress / 3;
            slen[1] = scalefac_compress % 3;
            slen[2] = 0;
            slen[3] = 0;

            channel.flags |= tables.PREFLAG;
            nsfb = tables.NSFB_TABLE[2][index];
        }
        
        var n = 0;
        for (var part = 0; part < 4; part++) {
            for (var i = 0; i < nsfb[part]; i++) {
                channel.scalefac[n++] = stream.read(slen[part]);
            }
        }
        
        while (n < 39) {
            channel.scalefac[n++] = 0;
        }
    } else {  // (mode_extension & tables.I_STEREO) && gr1ch (i.e. ch == 1)
        scalefac_compress >>>= 1;
        
        if (scalefac_compress < 180) {
            slen[0] =  scalefac_compress / 36;
            slen[1] = (scalefac_compress % 36) / 6;
            slen[2] = (scalefac_compress % 36) % 6;
            slen[3] = 0;

            nsfb = tables.NSFB_TABLE[3][index];
        } else if (scalefac_compress < 244) {
            scalefac_compress -= 180;

            slen[0] = (scalefac_compress % 64) >>> 4;
            slen[1] = (scalefac_compress % 16) >>> 2;
            slen[2] =  scalefac_compress %  4;
            slen[3] = 0;

            nsfb = tables.NSFB_TABLE[4][index];
        } else {
            scalefac_compress -= 244;

            slen[0] = scalefac_compress / 3;
            slen[1] = scalefac_compress % 3;
            slen[2] = 0;
            slen[3] = 0;

            nsfb = tables.NSFB_TABLE[5][index];
        }
        
        var n = 0;
        for (var part = 0; part < 4; ++part) {
            var max = (1 << slen[part]) - 1;
            for (var i = 0; i < nsfb[part]; ++i) {
                var is_pos = stream.read(slen[part]);

                channel.scalefac[n] = is_pos;
                gr1ch.scalefac[n++] = is_pos === max ? 1 : 0;
            }
        }
        
        while (n < 39) {
            channel.scalefac[n] = 0;
            gr1ch.scalefac[n++] = 0;  // apparently not illegal
        }
    }
    
    return stream.offset() - start;
};

Layer3.prototype.huffmanDecode = function(stream, xr, channel, sfbwidth, part2_length) {
    var exponents = this._exponents;
    var sfbwidthptr = 0;
    
    var bits_left = channel.part2_3_length - part2_length;    
    if (bits_left < 0)
        throw new Error('bad audio data length');
    
    this.exponents(channel, sfbwidth, exponents);
    
    var peek = stream.copy();
    stream.advance(bits_left);
    
    /* align bit reads to byte boundaries */
    var cachesz  = 8 - peek.bitPosition;
    cachesz += ((32 - 1 - 24) + (24 - cachesz)) & ~7;
    
    var bitcache = peek.read(cachesz);
    bits_left -= cachesz;

    var xrptr = 0;
    
    // big_values
    var region = 0;
    var reqcache = this.reqcache;
    
    var sfbound = xrptr + sfbwidth[sfbwidthptr++];
    var rcount  = channel.region0_count + 1;
    
    var entry = huffman.huff_pair_table[channel.table_select[region]];
    var table     = entry.table;
    var linbits   = entry.linbits;
    var startbits = entry.startbits;
    
    if (typeof table === 'undefined')
        throw new Error('bad Huffman table select');
        
    var expptr = 0;
    var exp = exponents[expptr++];
    var reqhits = 0;
    var big_values = channel.big_values;
    
    while (big_values-- && cachesz + bits_left > 0) {
         if (xrptr === sfbound) {
             sfbound += sfbwidth[sfbwidthptr++];

             // change table if region boundary
             if (--rcount === 0) {
                 if (region === 0)
                     rcount = channel.region1_count + 1;
                 else
                     rcount = 0; // all remaining

                 entry     = huffman.huff_pair_table[channel.table_select[++region]];
                 table     = entry.table;
                 linbits   = entry.linbits;
                 startbits = entry.startbits;

                 if (typeof table === 'undefined')
                     throw new Error('bad Huffman table select');
             }

             if (exp !== exponents[expptr]) {
                 exp = exponents[expptr];
                 reqhits = 0;
             }

             ++expptr;
         }
         
         if (cachesz < 21) {
             var bits   = ((32 - 1 - 21) + (21 - cachesz)) & ~7;
             bitcache   = (bitcache << bits) | peek.read(bits);
             cachesz   += bits;
             bits_left -= bits;
         }
         
         var clumpsz = startbits;
         var pair = table[ (((bitcache) >> ((cachesz) - (clumpsz))) & ((1 << (clumpsz)) - 1))];
         
         while (!pair.final) {
             cachesz -= clumpsz;
             clumpsz = pair.ptr.bits;
             pair    = table[pair.ptr.offset + (((bitcache) >> ((cachesz) - (clumpsz))) & ((1 << (clumpsz)) - 1))];
         }
         
         cachesz -= pair.value.hlen;
         
         if (linbits) {
             var value = pair.value.x;
             var x_final = false;
             
             switch (value) {
                 case 0:
                     xr[xrptr] = 0;
                     break;

                 case 15:
                     if (cachesz < linbits + 2) {
                         bitcache   = (bitcache << 16) | peek.read(16);
                         cachesz   += 16;
                         bits_left -= 16;
                     }

                     value += (((bitcache) >> ((cachesz) - (linbits))) & ((1 << (linbits)) - 1));
                     cachesz -= linbits;

                     requantized = this.requantize(value, exp);
                     x_final = true; // simulating goto, yay
                     break;

                 default:
                     if (reqhits & (1 << value)) {
                         requantized = reqcache[value];
                     } else {
                         reqhits |= (1 << value);
                         requantized = reqcache[value] = this.requantize(value, exp);
                     }
                     
                     x_final = true;
             }
             
             if(x_final) {
                 xr[xrptr] = ((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized;
             }
             
             value = pair.value.y;
             var y_final = false;
             
             switch (value) {
                 case 0:
                     xr[xrptr + 1] = 0;
                     break;

                 case 15:
                     if (cachesz < linbits + 1) {
                         bitcache   = (bitcache << 16) | peek.read(16);
                         cachesz   += 16;
                         bits_left -= 16;
                     }

                     value += (((bitcache) >> ((cachesz) - (linbits))) & ((1 << (linbits)) - 1));
                     cachesz -= linbits;

                     requantized = this.requantize(value, exp);
                     y_final = true;
                     break; // simulating goto, yayzor

                 default:
                     if (reqhits & (1 << value)) {
                         requantized = reqcache[value];
                     } else {
                         reqhits |= (1 << value);
                         reqcache[value] = this.requantize(value, exp);
                         requantized = reqcache[value];
                     }
                     
                     y_final = true;
             }
             
             if(y_final) {
                 xr[xrptr + 1] = ((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized;
             }
             
         } else {
             var value = pair.value.x;

             if (value === 0) {
                 xr[xrptr] = 0;
             } else {
                 if (reqhits & (1 << value))
                     requantized = reqcache[value];
                 else {
                     reqhits |= (1 << value);
                     requantized = reqcache[value] = this.requantize(value, exp);
                 }

                 xr[xrptr] = ((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized;
             }

             value = pair.value.y;

             if (value === 0) {
                 xr[xrptr + 1] = 0;
             } else {
                 if (reqhits & (1 << value))
                     requantized = reqcache[value];
                 else {
                     reqhits |= (1 << value);
                     requantized = reqcache[value] = this.requantize(value, exp);
                 }

                 xr[xrptr + 1] = ((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized;
             }
         }

         xrptr += 2;
    }
    
    if (cachesz + bits_left < 0)
        throw new Error('Huffman data overrun');
    
    // count1    
    var table = huffman.huff_quad_table[channel.flags & tables.COUNT1TABLE_SELECT];
    var requantized = this.requantize(1, exp);
    
    while (cachesz + bits_left > 0 && xrptr <= 572) {
        if (cachesz < 10) {
            bitcache   = (bitcache << 16) | peek.read(16);
            cachesz   += 16;
            bits_left -= 16;
        }
        
        var quad = table[(((bitcache) >> ((cachesz) - (4))) & ((1 << (4)) - 1))];
        
        // quad tables guaranteed to have at most one extra lookup
        if (!quad.final) {
            cachesz -= 4;
            quad = table[quad.ptr.offset + (((bitcache) >> ((cachesz) - (quad.ptr.bits))) & ((1 << (quad.ptr.bits)) - 1))];
        }
        
        cachesz -= quad.value.hlen;

        if (xrptr === sfbound) {
            sfbound += sfbwidth[sfbwidthptr++];

            if (exp !== exponents[expptr]) {
                exp = exponents[expptr];
                requantized = this.requantize(1, exp);
            }

            ++expptr;
        }
        
        // v (0..1)
        xr[xrptr] = quad.value.v ? (((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized) : 0;

        // w (0..1)
        xr[xrptr + 1] = quad.value.w ? (((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized) : 0;

        xrptr += 2;
        if (xrptr === sfbound) {
            sfbound += sfbwidth[sfbwidthptr++];

            if (exp !== exponents[expptr]) {
                exp = exponents[expptr];
                requantized = this.requantize(1, exp);
            }

            ++expptr;
        }
        
        // x (0..1)
        xr[xrptr] = quad.value.x ? (((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized) : 0;

        // y (0..1)
        xr[xrptr + 1] = quad.value.y ? (((bitcache) & (1 << ((cachesz--) - 1))) ? -requantized : requantized) : 0;

        xrptr += 2;
        
        if (cachesz + bits_left < 0) {
            // technically the bitstream is misformatted, but apparently
            // some encoders are just a bit sloppy with stuffing bits
            xrptr -= 4;
        }
    }
    
    if (-bits_left > MP3FrameHeader.BUFFER_GUARD * 8) {
        throw new Error("assertion failed: (-bits_left <= MP3FrameHeader.BUFFER_GUARD * CHAR_BIT)");
    }
    
    // rzero
    while (xrptr < 576) {
        xr[xrptr]     = 0;
        xr[xrptr + 1] = 0;
        xrptr += 2;
    }
};

Layer3.prototype.requantize = function(value, exp) {
    // usual (x >> 0) tricks to make sure frac and exp stay integers
    var frac = (exp % 4) >> 0;  // assumes sign(frac) === sign(exp)
    exp = (exp / 4) >> 0;

    var requantized = Math.pow(value, 4.0 / 3.0);
    requantized *= Math.pow(2.0, (exp / 4.0));
    
    if (frac) {
        requantized *= Math.pow(2.0, (frac / 4.0));
    }
    
    if (exp < 0) {
        requantized /= Math.pow(2.0, -exp * (3.0 / 4.0));
    }

    return requantized;
};

Layer3.prototype.exponents = function(channel, sfbwidth, exponents) {
    var gain = channel.global_gain - 210;
    var scalefac_multiplier = (channel.flags & tables.SCALEFAC_SCALE) ? 2 : 1;
    
    if (channel.block_type === 2) {
        var sfbi = 0, l = 0;
        
        if (channel.flags & tables.MIXED_BLOCK_FLAG) {
            var premask = (channel.flags & tables.PREFLAG) ? ~0 : 0;
            
            // long block subbands 0-1
            while (l < 36) {
                exponents[sfbi] = gain - ((channel.scalefac[sfbi] + (tables.PRETAB[sfbi] & premask)) << scalefac_multiplier);
                l += sfbwidth[sfbi++];
            }
        }
        
        // this is probably wrong for 8000 Hz short/mixed blocks
        var gain0 = gain - 8 * channel.subblock_gain[0];
        var gain1 = gain - 8 * channel.subblock_gain[1];
        var gain2 = gain - 8 * channel.subblock_gain[2];
        
        while (l < 576) {
            exponents[sfbi + 0] = gain0 - (channel.scalefac[sfbi + 0] << scalefac_multiplier);
            exponents[sfbi + 1] = gain1 - (channel.scalefac[sfbi + 1] << scalefac_multiplier);
            exponents[sfbi + 2] = gain2 - (channel.scalefac[sfbi + 2] << scalefac_multiplier);
            
            l += 3 * sfbwidth[sfbi];
            sfbi += 3;
        }
    } else {
        if (channel.flags & tables.PREFLAG) {
            for (var sfbi = 0; sfbi < 22; sfbi++) {
                exponents[sfbi] = gain - ((channel.scalefac[sfbi] + tables.PRETAB[sfbi]) << scalefac_multiplier);
            }
        } else {
            for (var sfbi = 0; sfbi < 22; sfbi++) {
                exponents[sfbi] = gain - (channel.scalefac[sfbi] << scalefac_multiplier);
            }
        }
    }
};

Layer3.prototype.stereo = function(xr, granules, gr, header, sfbwidth) {
    var granule = granules[gr];
    var modes = this.modes;
    var sfbi, l, n, i;
    
    if (granule.ch[0].block_type !== granule.ch[1].block_type || (granule.ch[0].flags & tables.MIXED_BLOCK_FLAG) !== (granule.ch[1].flags & tables.MIXED_BLOCK_FLAG))
        throw new Error('incompatible stereo block_type');
        
    for (var i = 0; i < 39; i++)
        modes[i] = header.mode_extension;
        
    // intensity stereo
    if (header.mode_extension & tables.I_STEREO) {
        var right_ch = granule.ch[1];
        var right_xr = xr[1];
        
        header.flags |= MP3FrameHeader.FLAGS.tables.I_STEREO;
         
        // first determine which scalefactor bands are to be processed
        if (right_ch.block_type === 2) {
            var lower, start, max, bound = new Uint32Array(3), w;

            lower = start = max = bound[0] = bound[1] = bound[2] = 0;
            sfbi = l = 0;
            
            if (right_ch.flags & tables.MIXED_BLOCK_FLAG) {
                while (l < 36) {
                    n = sfbwidth[sfbi++];

                    for (var i = 0; i < n; ++i) {
                        if (right_xr[i]) {
                            lower = sfbi;
                            break;
                        }
                    }

                    right_xr += n;
                    l += n;
                }

                start = sfbi;
            }
            
            var w = 0;
            while (l < 576) {
                n = sfbwidth[sfbi++];

                for (i = 0; i < n; ++i) {
                    if (right_xr[i]) {
                        max = bound[w] = sfbi;
                        break;
                    }
                }

                right_xr += n;
                l += n;
                w = (w + 1) % 3;
            }
            
            if (max)
                lower = start;

            // long blocks
            for (i = 0; i < lower; ++i)
                modes[i] = header.mode_extension & ~tables.I_STEREO;

            // short blocks
            w = 0;
            for (i = start; i < max; ++i) {
                if (i < bound[w])
                    modes[i] = header.mode_extension & ~tables.I_STEREO;

                w = (w + 1) % 3;
            }
        } else {
            var bound = 0;
            for (sfbi = l = 0; l < 576; l += n) {
                n = sfbwidth[sfbi++];

                for (i = 0; i < n; ++i) {
                    if (right_xr[i]) {
                        bound = sfbi;
                        break;
                    }
                }

                right_xr += n;
            }

            for (i = 0; i < bound; ++i)
                modes[i] = header.mode_extension & ~tables.I_STEREO;
        }
        
        // now do the actual processing
        if (header.flags & MP3FrameHeader.FLAGS.LSF_EXT) {
            var illegal_pos = granules[gr + 1].ch[1].scalefac;

            // intensity_scale
            var lsf_scale = IS_Ltables.SF_TABLE[right_ch.scalefac_compress & 0x1];
            
            for (sfbi = l = 0; l < 576; ++sfbi, l += n) {
                n = sfbwidth[sfbi];

                if (!(modes[sfbi] & tables.I_STEREO))
                    continue;

                if (illegal_pos[sfbi]) {
                    modes[sfbi] &= ~tables.I_STEREO;
                    continue;
                }

                is_pos = right_ch.scalefac[sfbi];
                
                for (i = 0; i < n; ++i) {
                    var left = xr[0][l + i];

                    if (is_pos === 0) {
                        xr[1][l + i] = left;
                    } else {
                        var opposite = left * lsf_scale[(is_pos - 1) / 2];

                        if (is_pos & 1) {
                            xr[0][l + i] = opposite;
                            xr[1][l + i] = left;
                        }
                        else {
                            xr[1][l + i] = opposite;
                        }
                    }
                }
            }
        } else {
            for (sfbi = l = 0; l < 576; ++sfbi, l += n) {
                n = sfbwidth[sfbi];

                if (!(modes[sfbi] & tables.I_STEREO))
                    continue;

                is_pos = right_ch.scalefac[sfbi];

                if (is_pos >= 7) {  // illegal intensity position
                    modes[sfbi] &= ~tables.I_STEREO;
                    continue;
                }

                for (i = 0; i < n; ++i) {
                    var left = xr[0][l + i];
                    xr[0][l + i] = left * tables.IS_TABLE[is_pos];
                    xr[1][l + i] = left * tables.IS_TABLE[6 - is_pos];
                }
            }
        }
    }
    
    // middle/side stereo
    if (header.mode_extension & tables.MS_STEREO) {
        header.flags |= tables.MS_STEREO;

        var invsqrt2 = tables.ROOT_TABLE[3 + -2];

        for (sfbi = l = 0; l < 576; ++sfbi, l += n) {
            n = sfbwidth[sfbi];

            if (modes[sfbi] !== tables.MS_STEREO)
                continue;

            for (i = 0; i < n; ++i) {
                var m = xr[0][l + i];
                var s = xr[1][l + i];

                xr[0][l + i] = (m + s) * invsqrt2;  // l = (m + s) / sqrt(2)
                xr[1][l + i] = (m - s) * invsqrt2;  // r = (m - s) / sqrt(2)
            }
        }
    }
};

Layer3.prototype.aliasreduce = function(xr, lines) {
    for (var xrPointer = 18; xrPointer < lines; xrPointer += 18) {
        for (var i = 0; i < 8; ++i) {
            var a = xr[xrPointer - i - 1];
            var b = xr[xrPointer + i];

            xr[xrPointer - i - 1] = a * tables.CS[i] - b * tables.CA[i];
            xr[xrPointer + i] = b * tables.CS[i] + a * tables.CA[i];
        }
    }
};

// perform IMDCT and windowing for long blocks
Layer3.prototype.imdct_l = function (X, z, block_type) {
    // IMDCT
    this.imdct.imdct36(X, z);

    // windowing
    switch (block_type) {
        case 0:  // normal window
            for (var i = 0; i < 36; ++i) z[i] = z[i] * tables.WINDOW_L[i];
            break;

        case 1:  // start block
            for (var i =  0; i < 18; ++i) z[i] = z[i] * tables.WINDOW_L[i];
            for (var i = 24; i < 30; ++i) z[i] = z[i] * tables.WINDOW_S[i - 18];
            for (var i = 30; i < 36; ++i) z[i] = 0;
            break;

        case 3:  // stop block
            for (var i =  0; i <  6; ++i) z[i] = 0;
            for (var i =  6; i < 12; ++i) z[i] = z[i] * tables.WINDOW_S[i - 6];
            for (var i = 18; i < 36; ++i) z[i] = z[i] * tables.WINDOW_L[i];
            break;
    }
};

/*
 * perform IMDCT and windowing for short blocks
 */
Layer3.prototype.imdct_s = function (X, z) {
    var yptr = 0;
    var wptr;
    var Xptr = 0;
    
    var y = new Float64Array(36);
    var hi, lo;

    // IMDCT
    for (var w = 0; w < 3; ++w) {
        var sptr = 0;

        for (var i = 0; i < 3; ++i) {
            lo = X[Xptr + 0] * IMDCT.S[sptr][0] +
                 X[Xptr + 1] * IMDCT.S[sptr][1] +
                 X[Xptr + 2] * IMDCT.S[sptr][2] +
                 X[Xptr + 3] * IMDCT.S[sptr][3] +
                 X[Xptr + 4] * IMDCT.S[sptr][4] +
                 X[Xptr + 5] * IMDCT.S[sptr][5];


            y[yptr + i + 0] = lo;
            y[yptr + 5 - i] = -y[yptr + i + 0];

            ++sptr;

            lo = X[Xptr + 0] * IMDCT.S[sptr][0] +
                 X[Xptr + 1] * IMDCT.S[sptr][1] +
                 X[Xptr + 2] * IMDCT.S[sptr][2] +
                 X[Xptr + 3] * IMDCT.S[sptr][3] +
                 X[Xptr + 4] * IMDCT.S[sptr][4] +
                 X[Xptr + 5] * IMDCT.S[sptr][5];

            y[yptr +  i + 6] = lo;
            y[yptr + 11 - i] = y[yptr + i + 6];

            ++sptr;
        }

        yptr += 12;
        Xptr += 6;
    }

    // windowing, overlapping and concatenation
    yptr = 0;
    var wptr = 0;

    for (var i = 0; i < 6; ++i) {
        z[i + 0] = 0;
        z[i + 6] = y[yptr +  0 + 0] * tables.WINDOW_S[wptr + 0];

        lo = y[yptr + 0 + 6] * tables.WINDOW_S[wptr + 6] +
             y[yptr + 12 + 0] * tables.WINDOW_S[wptr + 0];

        z[i + 12] = lo;

        lo = y[yptr + 12 + 6] * tables.WINDOW_S[wptr + 6] +
             y[yptr + 24 + 0] * tables.WINDOW_S[wptr + 0];

        z[i + 18] = lo;
        z[i + 24] = y[yptr + 24 + 6] * tables.WINDOW_S[wptr + 6];
        z[i + 30] = 0;

        ++yptr;
        ++wptr;
    }
};

Layer3.prototype.overlap = function (output, overlap, sample, sb) {
    for (var i = 0; i < 18; ++i) {
        sample[i][sb] = output[i] + overlap[i];
        overlap[i]    = output[i + 18];
    }
};

Layer3.prototype.freqinver = function (sample, sb) {
    for (var i = 1; i < 18; i += 2)
        sample[i][sb] = -sample[i][sb];
};

Layer3.prototype.overlap_z = function (overlap, sample, sb) {
    for (var i = 0; i < 18; ++i) {
        sample[i][sb] = overlap[i];
        overlap[i]    = 0;
    }
};

Layer3.prototype.reorder = function (xr, channel, sfbwidth) {
    var sfbwidthPointer = 0;
    var tmp = this.tmp;
    var sbw = new Uint32Array(3);
    var sw  = new Uint32Array(3);
    
    // this is probably wrong for 8000 Hz mixed blocks

    var sb = 0;
    if (channel.flags & tables.MIXED_BLOCK_FLAG) {
        var sb = 2;

        var l = 0;
        while (l < 36)
            l += sfbwidth[sfbwidthPointer++];
    }

    for (var w = 0; w < 3; ++w) {
        sbw[w] = sb;
        sw[w]  = 0;
    }

    f = sfbwidth[sfbwidthPointer++];
    w = 0;

    for (var l = 18 * sb; l < 576; ++l) {
        if (f-- === 0) {
            f = sfbwidth[sfbwidthPointer++] - 1;
            w = (w + 1) % 3;
        }
        
        tmp[sbw[w]][w][sw[w]++] = xr[l];

        if (sw[w] === 6) {
            sw[w] = 0;
            ++sbw[w];
        }
    }

    var tmp2 = this.tmp2;
    var ptr = 0;
    
    for (var i = 0; i < 32; i++) {
        for (var j = 0; j < 3; j++) {
            for (var k = 0; k < 6; k++) {
                tmp2[ptr++] = tmp[i][j][k];
            }
        }
    }
    
    var len = (576 - 18 * sb); 
    for (var i = 0; i < len; i++) {
        xr[18 * sb + i] = tmp2[sb + i];
    }
};

module.exports = Layer3;

},{"./frame":4,"./header":5,"./huffman":6,"./imdct":8,"./tables":14,"./utils":15}],12:[function(require,module,exports){
var AV = (window.AV);
var MP3FrameHeader = require('./header');

function MP3Stream(stream) {
    this.stream = stream;                     // actual bitstream
    this.sync = false;                        // stream sync found
    this.freerate = 0;                        // free bitrate (fixed)
    this.this_frame = stream.stream.offset;   // start of current frame
    this.next_frame = stream.stream.offset;   // start of next frame
    
    this.main_data = new Uint8Array(MP3FrameHeader.BUFFER_MDLEN); // actual audio data
    this.md_len = 0;                               // length of main data
    
    // copy methods from actual stream
    for (var key in stream) {
        if (typeof stream[key] === 'function')
            this[key] = stream[key].bind(stream);
    }
}

MP3Stream.prototype.getU8 = function(offset) {
    var stream = this.stream.stream;
    return stream.peekUInt8(offset - stream.offset);
};

MP3Stream.prototype.nextByte = function() {
    var stream = this.stream;
    return stream.bitPosition === 0 ? stream.stream.offset : stream.stream.offset + 1;
};

MP3Stream.prototype.doSync = function() {
    var stream = this.stream.stream;
    this.align();
    
    while (this.available(16) && !(stream.peekUInt8(0) === 0xff && (stream.peekUInt8(1) & 0xe0) === 0xe0)) {
        this.advance(8);
    }

    if (!this.available(MP3FrameHeader.BUFFER_GUARD))
        return false;
        
    return true;
};

MP3Stream.prototype.reset = function(byteOffset) {
    this.seek(byteOffset * 8);
    this.next_frame = byteOffset;
    this.sync = true;
};

module.exports = MP3Stream;

},{"./header":5}],13:[function(require,module,exports){
var utils = require('./utils');

function MP3Synth() {
    this.filter = utils.makeArray([2, 2, 2, 16, 8]); // polyphase filterbank outputs
    this.phase = 0;
    
    this.pcm = {
        samplerate: 0,
        channels: 0,
        length: 0,
        samples: [new Float64Array(1152), new Float64Array(1152)]
    };
}

/* costab[i] = cos(PI / (2 * 32) * i) */
const costab1  = 0.998795456;
const costab2  = 0.995184727;
const costab3  = 0.989176510;
const costab4  = 0.980785280;
const costab5  = 0.970031253;
const costab6  = 0.956940336;
const costab7  = 0.941544065;
const costab8  = 0.923879533;
const costab9  = 0.903989293;
const costab10 = 0.881921264;
const costab11 = 0.857728610;
const costab12 = 0.831469612;
const costab13 = 0.803207531;
const costab14 = 0.773010453;
const costab15 = 0.740951125;
const costab16 = 0.707106781;
const costab17 = 0.671558955;
const costab18 = 0.634393284;
const costab19 = 0.595699304;
const costab20 = 0.555570233;
const costab21 = 0.514102744;
const costab22 = 0.471396737;
const costab23 = 0.427555093;
const costab24 = 0.382683432;
const costab25 = 0.336889853;
const costab26 = 0.290284677;
const costab27 = 0.242980180;
const costab28 = 0.195090322;
const costab29 = 0.146730474;
const costab30 = 0.098017140;
const costab31 = 0.049067674;

/*
 * NAME:    dct32()
 * DESCRIPTION: perform fast in[32].out[32] DCT
 */
MP3Synth.dct32 = function (_in, slot, lo, hi) {
    var t0,   t1,   t2,   t3,   t4,   t5,   t6,   t7;
    var t8,   t9,   t10,  t11,  t12,  t13,  t14,  t15;
    var t16,  t17,  t18,  t19,  t20,  t21,  t22,  t23;
    var t24,  t25,  t26,  t27,  t28,  t29,  t30,  t31;
    var t32,  t33,  t34,  t35,  t36,  t37,  t38,  t39;
    var t40,  t41,  t42,  t43,  t44,  t45,  t46,  t47;
    var t48,  t49,  t50,  t51,  t52,  t53,  t54,  t55;
    var t56,  t57,  t58,  t59,  t60,  t61,  t62,  t63;
    var t64,  t65,  t66,  t67,  t68,  t69,  t70,  t71;
    var t72,  t73,  t74,  t75,  t76,  t77,  t78,  t79;
    var t80,  t81,  t82,  t83,  t84,  t85,  t86,  t87;
    var t88,  t89,  t90,  t91,  t92,  t93,  t94,  t95;
    var t96,  t97,  t98,  t99,  t100, t101, t102, t103;
    var t104, t105, t106, t107, t108, t109, t110, t111;
    var t112, t113, t114, t115, t116, t117, t118, t119;
    var t120, t121, t122, t123, t124, t125, t126, t127;
    var t128, t129, t130, t131, t132, t133, t134, t135;
    var t136, t137, t138, t139, t140, t141, t142, t143;
    var t144, t145, t146, t147, t148, t149, t150, t151;
    var t152, t153, t154, t155, t156, t157, t158, t159;
    var t160, t161, t162, t163, t164, t165, t166, t167;
    var t168, t169, t170, t171, t172, t173, t174, t175;
    var t176;

    t0   = _in[0]  + _in[31];  t16  = ((_in[0]  - _in[31]) * (costab1));
    t1   = _in[15] + _in[16];  t17  = ((_in[15] - _in[16]) * (costab31));

    t41  = t16 + t17;
    t59  = ((t16 - t17) * (costab2));
    t33  = t0  + t1;
    t50  = ((t0  - t1) * ( costab2));

    t2   = _in[7]  + _in[24];  t18  = ((_in[7]  - _in[24]) * (costab15));
    t3   = _in[8]  + _in[23];  t19  = ((_in[8]  - _in[23]) * (costab17));

    t42  = t18 + t19;
    t60  = ((t18 - t19) * (costab30));
    t34  = t2  + t3;
    t51  = ((t2  - t3) * ( costab30));

    t4   = _in[3]  + _in[28];  t20  = ((_in[3]  - _in[28]) * (costab7));
    t5   = _in[12] + _in[19];  t21  = ((_in[12] - _in[19]) * (costab25));

    t43  = t20 + t21;
    t61  = ((t20 - t21) * (costab14));
    t35  = t4  + t5;
    t52  = ((t4  - t5) * ( costab14));

    t6   = _in[4]  + _in[27];  t22  = ((_in[4]  - _in[27]) * (costab9));
    t7   = _in[11] + _in[20];  t23  = ((_in[11] - _in[20]) * (costab23));

    t44  = t22 + t23;
    t62  = ((t22 - t23) * (costab18));
    t36  = t6  + t7;
    t53  = ((t6  - t7) * ( costab18));

    t8   = _in[1]  + _in[30];  t24  = ((_in[1]  - _in[30]) * (costab3));
    t9   = _in[14] + _in[17];  t25  = ((_in[14] - _in[17]) * (costab29));

    t45  = t24 + t25;
    t63  = ((t24 - t25) * (costab6));
    t37  = t8  + t9;
    t54  = ((t8  - t9) * ( costab6));

    t10  = _in[6]  + _in[25];  t26  = ((_in[6]  - _in[25]) * (costab13));
    t11  = _in[9]  + _in[22];  t27  = ((_in[9]  - _in[22]) * (costab19));

    t46  = t26 + t27;
    t64  = ((t26 - t27) * (costab26));
    t38  = t10 + t11;
    t55  = ((t10 - t11) * (costab26));

    t12  = _in[2]  + _in[29];  t28  = ((_in[2]  - _in[29]) * (costab5));
    t13  = _in[13] + _in[18];  t29  = ((_in[13] - _in[18]) * (costab27));

    t47  = t28 + t29;
    t65  = ((t28 - t29) * (costab10));
    t39  = t12 + t13;
    t56  = ((t12 - t13) * (costab10));

    t14  = _in[5]  + _in[26];  t30  = ((_in[5]  - _in[26]) * (costab11));
    t15  = _in[10] + _in[21];  t31  = ((_in[10] - _in[21]) * (costab21));

    t48  = t30 + t31;
    t66  = ((t30 - t31) * (costab22));
    t40  = t14 + t15;
    t57  = ((t14 - t15) * (costab22));

    t69  = t33 + t34;  t89  = ((t33 - t34) * (costab4));
    t70  = t35 + t36;  t90  = ((t35 - t36) * (costab28));
    t71  = t37 + t38;  t91  = ((t37 - t38) * (costab12));
    t72  = t39 + t40;  t92  = ((t39 - t40) * (costab20));
    t73  = t41 + t42;  t94  = ((t41 - t42) * (costab4));
    t74  = t43 + t44;  t95  = ((t43 - t44) * (costab28));
    t75  = t45 + t46;  t96  = ((t45 - t46) * (costab12));
    t76  = t47 + t48;  t97  = ((t47 - t48) * (costab20));

    t78  = t50 + t51;  t100 = ((t50 - t51) * (costab4));
    t79  = t52 + t53;  t101 = ((t52 - t53) * (costab28));
    t80  = t54 + t55;  t102 = ((t54 - t55) * (costab12));
    t81  = t56 + t57;  t103 = ((t56 - t57) * (costab20));

    t83  = t59 + t60;  t106 = ((t59 - t60) * (costab4));
    t84  = t61 + t62;  t107 = ((t61 - t62) * (costab28));
    t85  = t63 + t64;  t108 = ((t63 - t64) * (costab12));
    t86  = t65 + t66;  t109 = ((t65 - t66) * (costab20));

    t113 = t69  + t70;
    t114 = t71  + t72;

    /*  0 */ hi[15][slot] = t113 + t114;
    /* 16 */ lo[ 0][slot] = ((t113 - t114) * (costab16));

    t115 = t73  + t74;
    t116 = t75  + t76;

    t32  = t115 + t116;

    /*  1 */ hi[14][slot] = t32;

    t118 = t78  + t79;
    t119 = t80  + t81;

    t58  = t118 + t119;

    /*  2 */ hi[13][slot] = t58;

    t121 = t83  + t84;
    t122 = t85  + t86;

    t67  = t121 + t122;

    t49  = (t67 * 2) - t32;

    /*  3 */ hi[12][slot] = t49;

    t125 = t89  + t90;
    t126 = t91  + t92;

    t93  = t125 + t126;

    /*  4 */ hi[11][slot] = t93;

    t128 = t94  + t95;
    t129 = t96  + t97;

    t98  = t128 + t129;

    t68  = (t98 * 2) - t49;

    /*  5 */ hi[10][slot] = t68;

    t132 = t100 + t101;
    t133 = t102 + t103;

    t104 = t132 + t133;

    t82  = (t104 * 2) - t58;

    /*  6 */ hi[ 9][slot] = t82;

    t136 = t106 + t107;
    t137 = t108 + t109;

    t110 = t136 + t137;

    t87  = (t110 * 2) - t67;

    t77  = (t87 * 2) - t68;

    /*  7 */ hi[ 8][slot] = t77;

    t141 = ((t69 - t70) * (costab8));
    t142 = ((t71 - t72) * (costab24));
    t143 = t141 + t142;

    /*  8 */ hi[ 7][slot] = t143;
    /* 24 */ lo[ 8][slot] =
        (((t141 - t142) * (costab16) * 2)) - t143;

    t144 = ((t73 - t74) * (costab8));
    t145 = ((t75 - t76) * (costab24));
    t146 = t144 + t145;

    t88  = (t146 * 2) - t77;

    /*  9 */ hi[ 6][slot] = t88;

    t148 = ((t78 - t79) * (costab8));
    t149 = ((t80 - t81) * (costab24));
    t150 = t148 + t149;

    t105 = (t150 * 2) - t82;

    /* 10 */ hi[ 5][slot] = t105;

    t152 = ((t83 - t84) * (costab8));
    t153 = ((t85 - t86) * (costab24));
    t154 = t152 + t153;

    t111 = (t154 * 2) - t87;

    t99  = (t111 * 2) - t88;

    /* 11 */ hi[ 4][slot] = t99;

    t157 = ((t89 - t90) * (costab8));
    t158 = ((t91 - t92) * (costab24));
    t159 = t157 + t158;

    t127 = (t159 * 2) - t93;

    /* 12 */ hi[ 3][slot] = t127;

    t160 = (((t125 - t126) * (costab16) * 2)) - t127;

    /* 20 */ lo[ 4][slot] = t160;
    /* 28 */ lo[12][slot] =
        (((((t157 - t158) * (costab16) * 2) - t159) * 2)) - t160;

    t161 = ((t94 - t95) * (costab8));
    t162 = ((t96 - t97) * (costab24));
    t163 = t161 + t162;

    t130 = (t163 * 2) - t98;

    t112 = (t130 * 2) - t99;

    /* 13 */ hi[ 2][slot] = t112;

    t164 = (((t128 - t129) * (costab16) * 2)) - t130;

    t166 = ((t100 - t101) * (costab8));
    t167 = ((t102 - t103) * (costab24));
    t168 = t166 + t167;

    t134 = (t168 * 2) - t104;

    t120 = (t134 * 2) - t105;

    /* 14 */ hi[ 1][slot] = t120;

    t135 = (((t118 - t119) * (costab16) * 2)) - t120;

    /* 18 */ lo[ 2][slot] = t135;

    t169 = (((t132 - t133) * (costab16) * 2)) - t134;

    t151 = (t169 * 2) - t135;

    /* 22 */ lo[ 6][slot] = t151;

    t170 = (((((t148 - t149) * (costab16) * 2) - t150) * 2)) - t151;

    /* 26 */ lo[10][slot] = t170;
    /* 30 */ lo[14][slot] =
        (((((((t166 - t167) * (costab16)) * 2 -
             t168) * 2) - t169) * 2) - t170);

    t171 = ((t106 - t107) * (costab8));
    t172 = ((t108 - t109) * (costab24));
    t173 = t171 + t172;

    t138 = (t173 * 2) - t110;
    t123 = (t138 * 2) - t111;
    t139 = (((t121 - t122) * (costab16) * 2)) - t123;
    t117 = (t123 * 2) - t112;

    /* 15 */ hi[ 0][slot] = t117;

    t124 = (((t115 - t116) * (costab16) * 2)) - t117;

    /* 17 */ lo[ 1][slot] = t124;

    t131 = (t139 * 2) - t124;

    /* 19 */ lo[ 3][slot] = t131;

    t140 = (t164 * 2) - t131;

    /* 21 */ lo[ 5][slot] = t140;

    t174 = (((t136 - t137) * (costab16) * 2)) - t138;
    t155 = (t174 * 2) - t139;
    t147 = (t155 * 2) - t140;

    /* 23 */ lo[ 7][slot] = t147;

    t156 = (((((t144 - t145) * (costab16) * 2) - t146) * 2)) - t147;

    /* 25 */ lo[ 9][slot] = t156;

    t175 = (((((t152 - t153) * (costab16) * 2) - t154) * 2)) - t155;
    t165 = (t175 * 2) - t156;

    /* 27 */ lo[11][slot] = t165;

    t176 = (((((((t161 - t162) * (costab16) * 2)) -
               t163) * 2) - t164) * 2) - t165;

    /* 29 */ lo[13][slot] = t176;
    /* 31 */ lo[15][slot] =
        (((((((((t171 - t172) * (costab16)) * 2 -
               t173) * 2) - t174) * 2) - t175) * 2) - t176);

    /*
     * Totals:
     *  80 multiplies
     *  80 additions
     * 119 subtractions
     *  49 shifts (not counting SSO)
     */
};

/*
 * These are the coefficients for the subband synthesis window. This is a
 * reordered version of Table B.3 from ISO/IEC 11172-3.
 */
const D = [
    [  0.000000000,   /*  0 */
       -0.000442505,
       0.003250122,
       -0.007003784,
       0.031082153,
       -0.078628540,
       0.100311279,
       -0.572036743,
       1.144989014,
       0.572036743,
       0.100311279,
       0.078628540,
       0.031082153,
       0.007003784,
       0.003250122,
       0.000442505,

       0.000000000,
       -0.000442505,
       0.003250122,
       -0.007003784,
       0.031082153,
       -0.078628540,
       0.100311279,
       -0.572036743,
       1.144989014,
       0.572036743,
       0.100311279,
       0.078628540,
       0.031082153,
       0.007003784,
       0.003250122,
       0.000442505 ],

    [ -0.000015259,   /*  1 */
      -0.000473022,
      0.003326416,
      -0.007919312,
      0.030517578,
      -0.084182739,
      0.090927124,
      -0.600219727,
      1.144287109,
      0.543823242,
      0.108856201,
      0.073059082,
      0.031478882,
      0.006118774,
      0.003173828,
      0.000396729,

      -0.000015259,
      -0.000473022,
      0.003326416,
      -0.007919312,
      0.030517578,
      -0.084182739,
      0.090927124,
      -0.600219727,
      1.144287109,
      0.543823242,
      0.108856201,
      0.073059082,
      0.031478882,
      0.006118774,
      0.003173828,
      0.000396729 ],

    [ -0.000015259,   /*  2 */
      -0.000534058,
      0.003387451,
      -0.008865356,
      0.029785156,
      -0.089706421,
      0.080688477,
      -0.628295898,
      1.142211914,
      0.515609741,
      0.116577148,
      0.067520142,
      0.031738281,
      0.005294800,
      0.003082275,
      0.000366211,

      -0.000015259,
      -0.000534058,
      0.003387451,
      -0.008865356,
      0.029785156,
      -0.089706421,
      0.080688477,
      -0.628295898,
      1.142211914,
      0.515609741,
      0.116577148,
      0.067520142,
      0.031738281,
      0.005294800,
      0.003082275,
      0.000366211 ],

    [ -0.000015259,   /*  3 */
      -0.000579834,
      0.003433228,
      -0.009841919,
      0.028884888,
      -0.095169067,
      0.069595337,
      -0.656219482,
      1.138763428,
      0.487472534,
      0.123474121,
      0.061996460,
      0.031845093,
      0.004486084,
      0.002990723,
      0.000320435,

      -0.000015259,
      -0.000579834,
      0.003433228,
      -0.009841919,
      0.028884888,
      -0.095169067,
      0.069595337,
      -0.656219482,
      1.138763428,
      0.487472534,
      0.123474121,
      0.061996460,
      0.031845093,
      0.004486084,
      0.002990723,
      0.000320435 ],

    [ -0.000015259,   /*  4 */
      -0.000625610,
      0.003463745,
      -0.010848999,
      0.027801514,
      -0.100540161,
      0.057617187,
      -0.683914185,
      1.133926392,
      0.459472656,
      0.129577637,
      0.056533813,
      0.031814575,
      0.003723145,
      0.002899170,
      0.000289917,

      -0.000015259,
      -0.000625610,
      0.003463745,
      -0.010848999,
      0.027801514,
      -0.100540161,
      0.057617187,
      -0.683914185,
      1.133926392,
      0.459472656,
      0.129577637,
      0.056533813,
      0.031814575,
      0.003723145,
      0.002899170,
      0.000289917 ],

    [ -0.000015259,   /*  5 */
      -0.000686646,
      0.003479004,
      -0.011886597,
      0.026535034,
      -0.105819702,
      0.044784546,
      -0.711318970,
      1.127746582,
      0.431655884,
      0.134887695,
      0.051132202,
      0.031661987,
      0.003005981,
      0.002792358,
      0.000259399,

      -0.000015259,
      -0.000686646,
      0.003479004,
      -0.011886597,
      0.026535034,
      -0.105819702,
      0.044784546,
      -0.711318970,
      1.127746582,
      0.431655884,
      0.134887695,
      0.051132202,
      0.031661987,
      0.003005981,
      0.002792358,
      0.000259399 ],

    [ -0.000015259,   /*  6 */
      -0.000747681,
      0.003479004,
      -0.012939453,
      0.025085449,
      -0.110946655,
      0.031082153,
      -0.738372803,
      1.120223999,
      0.404083252,
      0.139450073,
      0.045837402,
      0.031387329,
      0.002334595,
      0.002685547,
      0.000244141,

      -0.000015259,
      -0.000747681,
      0.003479004,
      -0.012939453,
      0.025085449,
      -0.110946655,
      0.031082153,
      -0.738372803,
      1.120223999,
      0.404083252,
      0.139450073,
      0.045837402,
      0.031387329,
      0.002334595,
      0.002685547,
      0.000244141 ],

    [ -0.000030518,   /*  7 */
      -0.000808716,
      0.003463745,
      -0.014022827,
      0.023422241,
      -0.115921021,
      0.016510010,
      -0.765029907,
      1.111373901,
      0.376800537,
      0.143264771,
      0.040634155,
      0.031005859,
      0.001693726,
      0.002578735,
      0.000213623,

      -0.000030518,
      -0.000808716,
      0.003463745,
      -0.014022827,
      0.023422241,
      -0.115921021,
      0.016510010,
      -0.765029907,
      1.111373901,
      0.376800537,
      0.143264771,
      0.040634155,
      0.031005859,
      0.001693726,
      0.002578735,
      0.000213623 ],

    [ -0.000030518,   /*  8 */
      -0.000885010,
      0.003417969,
      -0.015121460,
      0.021575928,
      -0.120697021,
      0.001068115,
      -0.791213989,
      1.101211548,
      0.349868774,
      0.146362305,
      0.035552979,
      0.030532837,
      0.001098633,
      0.002456665,
      0.000198364,

      -0.000030518,
      -0.000885010,
      0.003417969,
      -0.015121460,
      0.021575928,
      -0.120697021,
      0.001068115,
      -0.791213989,
      1.101211548,
      0.349868774,
      0.146362305,
      0.035552979,
      0.030532837,
      0.001098633,
      0.002456665,
      0.000198364 ],

    [ -0.000030518,   /*  9 */
      -0.000961304,
      0.003372192,
      -0.016235352,
      0.019531250,
      -0.125259399,
      -0.015228271,
      -0.816864014,
      1.089782715,
      0.323318481,
      0.148773193,
      0.030609131,
      0.029937744,
      0.000549316,
      0.002349854,
      0.000167847,

      -0.000030518,
      -0.000961304,
      0.003372192,
      -0.016235352,
      0.019531250,
      -0.125259399,
      -0.015228271,
      -0.816864014,
      1.089782715,
      0.323318481,
      0.148773193,
      0.030609131,
      0.029937744,
      0.000549316,
      0.002349854,
      0.000167847 ],

    [ -0.000030518,   /* 10 */
      -0.001037598,
      0.003280640,
      -0.017349243,
      0.017257690,
      -0.129562378,
      -0.032379150,
      -0.841949463,
      1.077117920,
      0.297210693,
      0.150497437,
      0.025817871,
      0.029281616,
      0.000030518,
      0.002243042,
      0.000152588,

      -0.000030518,
      -0.001037598,
      0.003280640,
      -0.017349243,
      0.017257690,
      -0.129562378,
      -0.032379150,
      -0.841949463,
      1.077117920,
      0.297210693,
      0.150497437,
      0.025817871,
      0.029281616,
      0.000030518,
      0.002243042,
      0.000152588 ],

    [ -0.000045776,   /* 11 */
      -0.001113892,
      0.003173828,
      -0.018463135,
      0.014801025,
      -0.133590698,
      -0.050354004,
      -0.866363525,
      1.063217163,
      0.271591187,
      0.151596069,
      0.021179199,
      0.028533936,
      -0.000442505,
      0.002120972,
      0.000137329,

      -0.000045776,
      -0.001113892,
      0.003173828,
      -0.018463135,
      0.014801025,
      -0.133590698,
      -0.050354004,
      -0.866363525,
      1.063217163,
      0.271591187,
      0.151596069,
      0.021179199,
      0.028533936,
      -0.000442505,
      0.002120972,
      0.000137329 ],

    [ -0.000045776,   /* 12 */
      -0.001205444,
      0.003051758,
      -0.019577026,
      0.012115479,
      -0.137298584,
      -0.069168091,
      -0.890090942,
      1.048156738,
      0.246505737,
      0.152069092,
      0.016708374,
      0.027725220,
      -0.000869751,
      0.002014160,
      0.000122070,

      -0.000045776,
      -0.001205444,
      0.003051758,
      -0.019577026,
      0.012115479,
      -0.137298584,
      -0.069168091,
      -0.890090942,
      1.048156738,
      0.246505737,
      0.152069092,
      0.016708374,
      0.027725220,
      -0.000869751,
      0.002014160,
      0.000122070 ],

    [ -0.000061035,   /* 13 */
      -0.001296997,
      0.002883911,
      -0.020690918,
      0.009231567,
      -0.140670776,
      -0.088775635,
      -0.913055420,
      1.031936646,
      0.221984863,
      0.151962280,
      0.012420654,
      0.026840210,
      -0.001266479,
      0.001907349,
      0.000106812,

      -0.000061035,
      -0.001296997,
      0.002883911,
      -0.020690918,
      0.009231567,
      -0.140670776,
      -0.088775635,
      -0.913055420,
      1.031936646,
      0.221984863,
      0.151962280,
      0.012420654,
      0.026840210,
      -0.001266479,
      0.001907349,
      0.000106812 ],

    [ -0.000061035,   /* 14 */
      -0.001388550,
      0.002700806,
      -0.021789551,
      0.006134033,
      -0.143676758,
      -0.109161377,
      -0.935195923,
      1.014617920,
      0.198059082,
      0.151306152,
      0.008316040,
      0.025909424,
      -0.001617432,
      0.001785278,
      0.000106812,

      -0.000061035,
      -0.001388550,
      0.002700806,
      -0.021789551,
      0.006134033,
      -0.143676758,
      -0.109161377,
      -0.935195923,
      1.014617920,
      0.198059082,
      0.151306152,
      0.008316040,
      0.025909424,
      -0.001617432,
      0.001785278,
      0.000106812 ],

    [ -0.000076294,   /* 15 */
      -0.001480103,
      0.002487183,
      -0.022857666,
      0.002822876,
      -0.146255493,
      -0.130310059,
      -0.956481934,
      0.996246338,
      0.174789429,
      0.150115967,
      0.004394531,
      0.024932861,
      -0.001937866,
      0.001693726,
      0.000091553,

      -0.000076294,
      -0.001480103,
      0.002487183,
      -0.022857666,
      0.002822876,
      -0.146255493,
      -0.130310059,
      -0.956481934,
      0.996246338,
      0.174789429,
      0.150115967,
      0.004394531,
      0.024932861,
      -0.001937866,
      0.001693726,
      0.000091553 ],

    [ -0.000076294,   /* 16 */
      -0.001586914,
      0.002227783,
      -0.023910522,
      -0.000686646,
      -0.148422241,
      -0.152206421,
      -0.976852417,
      0.976852417,
      0.152206421,
      0.148422241,
      0.000686646,
      0.023910522,
      -0.002227783,
      0.001586914,
      0.000076294,

      -0.000076294,
      -0.001586914,
      0.002227783,
      -0.023910522,
      -0.000686646,
      -0.148422241,
      -0.152206421,
      -0.976852417,
      0.976852417,
      0.152206421,
      0.148422241,
      0.000686646,
      0.023910522,
      -0.002227783,
      0.001586914,
      0.000076294 ]
];

/*
 * perform full frequency PCM synthesis
 */
MP3Synth.prototype.full = function(frame, nch, ns) {
    var Dptr, hi, lo, ptr;
    
    for (var ch = 0; ch < nch; ++ch) {
        var sbsample = frame.sbsample[ch];
        var filter  = this.filter[ch];
        var phase   = this.phase;
        var pcm     = this.pcm.samples[ch];
        var pcm1Ptr = 0;
        var pcm2Ptr = 0;

        for (var s = 0; s < ns; ++s) {
            MP3Synth.dct32(sbsample[s], phase >> 1, filter[0][phase & 1], filter[1][phase & 1]);

            var pe = phase & ~1;
            var po = ((phase - 1) & 0xf) | 1;

            /* calculate 32 samples */
            var fe = filter[0][ phase & 1];
            var fx = filter[0][~phase & 1];
            var fo = filter[1][~phase & 1];

            var fePtr = 0;
            var fxPtr = 0;
            var foPtr = 0;
            
            Dptr = 0;

            ptr = D[Dptr];
            _fx = fx[fxPtr];
            _fe = fe[fePtr];

            lo =  _fx[0] * ptr[po +  0];
            lo += _fx[1] * ptr[po + 14];
            lo += _fx[2] * ptr[po + 12];
            lo += _fx[3] * ptr[po + 10];
            lo += _fx[4] * ptr[po +  8];
            lo += _fx[5] * ptr[po +  6];
            lo += _fx[6] * ptr[po +  4];
            lo += _fx[7] * ptr[po +  2];
            lo = -lo;                      
            
            lo += _fe[0] * ptr[pe +  0];
            lo += _fe[1] * ptr[pe + 14];
            lo += _fe[2] * ptr[pe + 12];
            lo += _fe[3] * ptr[pe + 10];
            lo += _fe[4] * ptr[pe +  8];
            lo += _fe[5] * ptr[pe +  6];
            lo += _fe[6] * ptr[pe +  4];
            lo += _fe[7] * ptr[pe +  2];

            pcm[pcm1Ptr++] = lo;
            pcm2Ptr = pcm1Ptr + 30;

            for (var sb = 1; sb < 16; ++sb) {
                ++fePtr;
                ++Dptr;

                /* D[32 - sb][i] === -D[sb][31 - i] */

                ptr = D[Dptr];
                _fo = fo[foPtr];
                _fe = fe[fePtr];

                lo  = _fo[0] * ptr[po +  0];
                lo += _fo[1] * ptr[po + 14];
                lo += _fo[2] * ptr[po + 12];
                lo += _fo[3] * ptr[po + 10];
                lo += _fo[4] * ptr[po +  8];
                lo += _fo[5] * ptr[po +  6];
                lo += _fo[6] * ptr[po +  4];
                lo += _fo[7] * ptr[po +  2];
                lo = -lo;

                lo += _fe[7] * ptr[pe + 2];
                lo += _fe[6] * ptr[pe + 4];
                lo += _fe[5] * ptr[pe + 6];
                lo += _fe[4] * ptr[pe + 8];
                lo += _fe[3] * ptr[pe + 10];
                lo += _fe[2] * ptr[pe + 12];
                lo += _fe[1] * ptr[pe + 14];
                lo += _fe[0] * ptr[pe + 0];

                pcm[pcm1Ptr++] = lo;

                lo =  _fe[0] * ptr[-pe + 31 - 16];
                lo += _fe[1] * ptr[-pe + 31 - 14];
                lo += _fe[2] * ptr[-pe + 31 - 12];
                lo += _fe[3] * ptr[-pe + 31 - 10];
                lo += _fe[4] * ptr[-pe + 31 -  8];
                lo += _fe[5] * ptr[-pe + 31 -  6];
                lo += _fe[6] * ptr[-pe + 31 -  4];
                lo += _fe[7] * ptr[-pe + 31 -  2];

                lo += _fo[7] * ptr[-po + 31 -  2];
                lo += _fo[6] * ptr[-po + 31 -  4];
                lo += _fo[5] * ptr[-po + 31 -  6];
                lo += _fo[4] * ptr[-po + 31 -  8];
                lo += _fo[3] * ptr[-po + 31 - 10];
                lo += _fo[2] * ptr[-po + 31 - 12];
                lo += _fo[1] * ptr[-po + 31 - 14];
                lo += _fo[0] * ptr[-po + 31 - 16];

                pcm[pcm2Ptr--] = lo;
                ++foPtr;
            }

            ++Dptr;

            ptr = D[Dptr];
            _fo = fo[foPtr];

            lo  = _fo[0] * ptr[po +  0];
            lo += _fo[1] * ptr[po + 14];
            lo += _fo[2] * ptr[po + 12];
            lo += _fo[3] * ptr[po + 10];
            lo += _fo[4] * ptr[po +  8];
            lo += _fo[5] * ptr[po +  6];
            lo += _fo[6] * ptr[po +  4];
            lo += _fo[7] * ptr[po +  2];

            pcm[pcm1Ptr] = -lo;
            pcm1Ptr += 16;
            phase = (phase + 1) % 16;
        }
    }
};

// TODO: synth.half()

/*
 * NAME:    synth.frame()
 * DESCRIPTION: perform PCM synthesis of frame subband samples
 */
MP3Synth.prototype.frame = function (frame) {
    var nch = frame.header.nchannels();
    var ns  = frame.header.nbsamples();

    this.pcm.samplerate = frame.header.samplerate;
    this.pcm.channels   = nch;
    this.pcm.length     = 32 * ns;

    /*
     if (frame.options & Mad.Option.HALFSAMPLERATE) {
     this.pcm.samplerate /= 2;
     this.pcm.length     /= 2;

     throw new Error("HALFSAMPLERATE is not supported. What do you think? As if I have the time for this");
     }
     */

    this.full(frame, nch, ns);
    this.phase = (this.phase + ns) % 16;
};

module.exports = MP3Synth;

},{"./utils":15}],14:[function(require,module,exports){
/*
 * These are the scalefactor values for Layer I and Layer II.
 * The values are from Table B.1 of ISO/IEC 11172-3.
 *
 * Strictly speaking, Table B.1 has only 63 entries (0-62), thus a strict
 * interpretation of ISO/IEC 11172-3 would suggest that a scalefactor index of
 * 63 is invalid. However, for better compatibility with current practices, we
 * add a 64th entry.
 */
exports.SF_TABLE = new Float32Array([
    2.000000000000, 1.587401051968, 1.259921049895, 1.000000000000, 
    0.793700525984, 0.629960524947, 0.500000000000, 0.396850262992,
    0.314980262474, 0.250000000000, 0.198425131496, 0.157490131237,
    0.125000000000, 0.099212565748, 0.078745065618, 0.062500000000,
    0.049606282874, 0.039372532809, 0.031250000000, 0.024803141437,
    0.019686266405, 0.015625000000, 0.012401570719, 0.009843133202,
    0.007812500000, 0.006200785359, 0.004921566601, 0.003906250000,
    0.003100392680, 0.002460783301, 0.001953125000, 0.001550196340,
    0.001230391650, 0.000976562500, 0.000775098170, 0.000615195825,
    0.000488281250, 0.000387549085, 0.000307597913, 0.000244140625,
    0.000193774542, 0.000153798956, 0.000122070313, 0.000096887271,
    0.000076899478, 0.000061035156, 0.000048443636, 0.000038449739,
    0.000030517578, 0.000024221818, 0.000019224870, 0.000015258789,
    0.000012110909, 0.000009612435, 0.000007629395, 0.000006055454,
    0.000004806217, 0.000003814697, 0.000003027727, 0.000002403109,
    0.000001907349, 0.000001513864, 0.000001201554, 0.000000000000
]);

/*
 * MPEG-1 scalefactor band widths
 * derived from Table B.8 of ISO/IEC 11172-3
 */
const SFB_48000_LONG = new Uint8Array([
    4,  4,  4,  4,  4,  4,  6,  6,  6,   8,  10,
    12, 16, 18, 22, 28, 34, 40, 46, 54,  54, 192
]);

const SFB_44100_LONG = new Uint8Array([
    4,  4,  4,  4,  4,  4,  6,  6,  8,   8,  10,
    12, 16, 20, 24, 28, 34, 42, 50, 54,  76, 158
]);

const SFB_32000_LONG = new Uint8Array([
    4,  4,  4,  4,  4,  4,  6,  6,  8,  10,  12,
    16, 20, 24, 30, 38, 46, 56, 68, 84, 102,  26
]);

const SFB_48000_SHORT = new Uint8Array([
    4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  6,
    6,  6,  6,  6,  6, 10, 10, 10, 12, 12, 12, 14, 14,
    14, 16, 16, 16, 20, 20, 20, 26, 26, 26, 66, 66, 66
]);

const SFB_44100_SHORT = new Uint8Array([
    4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  6,
    6,  6,  8,  8,  8, 10, 10, 10, 12, 12, 12, 14, 14,
    14, 18, 18, 18, 22, 22, 22, 30, 30, 30, 56, 56, 56
]);

const SFB_32000_SHORT = new Uint8Array([
    4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  4,  6,
    6,  6,  8,  8,  8, 12, 12, 12, 16, 16, 16, 20, 20,
    20, 26, 26, 26, 34, 34, 34, 42, 42, 42, 12, 12, 12
]);

const SFB_48000_MIXED = new Uint8Array([
    /* long */   4,  4,  4,  4,  4,  4,  6,  6,
    /* short */  4,  4,  4,  6,  6,  6,  6,  6,  6, 10,
    10, 10, 12, 12, 12, 14, 14, 14, 16, 16,
    16, 20, 20, 20, 26, 26, 26, 66, 66, 66
]);

const SFB_44100_MIXED = new Uint8Array([
    /* long */   4,  4,  4,  4,  4,  4,  6,  6,
    /* short */  4,  4,  4,  6,  6,  6,  8,  8,  8, 10,
    10, 10, 12, 12, 12, 14, 14, 14, 18, 18,
    18, 22, 22, 22, 30, 30, 30, 56, 56, 56
]);

const SFB_32000_MIXED = new Uint8Array([
    /* long */   4,  4,  4,  4,  4,  4,  6,  6,
    /* short */  4,  4,  4,  6,  6,  6,  8,  8,  8, 12,
    12, 12, 16, 16, 16, 20, 20, 20, 26, 26,
    26, 34, 34, 34, 42, 42, 42, 12, 12, 12
]);

/*
 * MPEG-2 scalefactor band widths
 * derived from Table B.2 of ISO/IEC 13818-3
 */
const SFB_24000_LONG = new Uint8Array([
    6,  6,  6,  6,  6,  6,  8, 10, 12,  14,  16,
   18, 22, 26, 32, 38, 46, 54, 62, 70,  76,  36
]);

const SFB_22050_LONG = new Uint8Array([
    6,  6,  6,  6,  6,  6,  8, 10, 12,  14,  16,
   20, 24, 28, 32, 38, 46, 52, 60, 68,  58,  54
]);

const SFB_16000_LONG = SFB_22050_LONG;

const SFB_24000_SHORT = new Uint8Array([
   4,  4,  4,  4,  4,  4,  4,  4,  4,  6,  6,  6,  8,
   8,  8, 10, 10, 10, 12, 12, 12, 14, 14, 14, 18, 18,
  18, 24, 24, 24, 32, 32, 32, 44, 44, 44, 12, 12, 12
]);

const SFB_22050_SHORT = new Uint8Array([
   4,  4,  4,  4,  4,  4,  4,  4,  4,  6,  6,  6,  6,
   6,  6,  8,  8,  8, 10, 10, 10, 14, 14, 14, 18, 18,
  18, 26, 26, 26, 32, 32, 32, 42, 42, 42, 18, 18, 18
]);

const SFB_16000_SHORT = new Uint8Array([
   4,  4,  4,  4,  4,  4,  4,  4,  4,  6,  6,  6,  8,
   8,  8, 10, 10, 10, 12, 12, 12, 14, 14, 14, 18, 18,
  18, 24, 24, 24, 30, 30, 30, 40, 40, 40, 18, 18, 18
]);

const SFB_24000_MIXED = new Uint8Array([
  /* long */   6,  6,  6,  6,  6,  6,
  /* short */  6,  6,  6,  8,  8,  8, 10, 10, 10, 12,
              12, 12, 14, 14, 14, 18, 18, 18, 24, 24,
              24, 32, 32, 32, 44, 44, 44, 12, 12, 12
]);

const SFB_22050_MIXED = new Uint8Array([
  /* long */   6,  6,  6,  6,  6,  6,
  /* short */  6,  6,  6,  6,  6,  6,  8,  8,  8, 10,
              10, 10, 14, 14, 14, 18, 18, 18, 26, 26,
              26, 32, 32, 32, 42, 42, 42, 18, 18, 18
]);

const SFB_16000_MIXED = new Uint8Array([
  /* long */   6,  6,  6,  6,  6,  6,
  /* short */  6,  6,  6,  8,  8,  8, 10, 10, 10, 12,
              12, 12, 14, 14, 14, 18, 18, 18, 24, 24,
              24, 30, 30, 30, 40, 40, 40, 18, 18, 18
]);

/*
 * MPEG 2.5 scalefactor band widths
 * derived from public sources
 */
const SFB_12000_LONG = SFB_16000_LONG;
const SFB_11025_LONG = SFB_12000_LONG;

const SFB_8000_LONG = new Uint8Array([
  12, 12, 12, 12, 12, 12, 16, 20, 24,  28,  32,
  40, 48, 56, 64, 76, 90,  2,  2,  2,   2,   2
]);

const SFB_12000_SHORT = SFB_16000_SHORT;
const SFB_11025_SHORT = SFB_12000_SHORT;

const SFB_8000_SHORT = new Uint8Array([
   8,  8,  8,  8,  8,  8,  8,  8,  8, 12, 12, 12, 16,
  16, 16, 20, 20, 20, 24, 24, 24, 28, 28, 28, 36, 36,
  36,  2,  2,  2,  2,  2,  2,  2,  2,  2, 26, 26, 26
]);

const SFB_12000_MIXED = SFB_16000_MIXED;
const SFB_11025_MIXED = SFB_12000_MIXED;

/* the 8000 Hz short block scalefactor bands do not break after
   the first 36 frequency lines, so this is probably wrong */
const SFB_8000_MIXED = new Uint8Array([
  /* long */  12, 12, 12,
  /* short */  4,  4,  4,  8,  8,  8, 12, 12, 12, 16, 16, 16,
              20, 20, 20, 24, 24, 24, 28, 28, 28, 36, 36, 36,
               2,  2,  2,  2,  2,  2,  2,  2,  2, 26, 26, 26
]);

exports.SFBWIDTH_TABLE = [
    { l: SFB_48000_LONG, s: SFB_48000_SHORT, m: SFB_48000_MIXED },
    { l: SFB_44100_LONG, s: SFB_44100_SHORT, m: SFB_44100_MIXED },
    { l: SFB_32000_LONG, s: SFB_32000_SHORT, m: SFB_32000_MIXED },
    { l: SFB_24000_LONG, s: SFB_24000_SHORT, m: SFB_24000_MIXED },
    { l: SFB_22050_LONG, s: SFB_22050_SHORT, m: SFB_22050_MIXED },
    { l: SFB_16000_LONG, s: SFB_16000_SHORT, m: SFB_16000_MIXED },
    { l: SFB_12000_LONG, s: SFB_12000_SHORT, m: SFB_12000_MIXED },
    { l: SFB_11025_LONG, s: SFB_11025_SHORT, m: SFB_11025_MIXED },
    { l:  SFB_8000_LONG, s:  SFB_8000_SHORT, m:  SFB_8000_MIXED }
];

exports.PRETAB = new Uint8Array([
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 3, 3, 3, 2, 0
]);

/*
 * fractional powers of two
 * used for requantization and joint stereo decoding
 *
 * ROOT_TABLE[3 + x] = 2^(x/4)
 */
exports.ROOT_TABLE = new Float32Array([
    /* 2^(-3/4) */ 0.59460355750136,
    /* 2^(-2/4) */ 0.70710678118655,
    /* 2^(-1/4) */ 0.84089641525371,
    /* 2^( 0/4) */ 1.00000000000000,
    /* 2^(+1/4) */ 1.18920711500272,
    /* 2^(+2/4) */ 1.41421356237310,
    /* 2^(+3/4) */ 1.68179283050743
]);

exports.CS = new Float32Array([
    +0.857492926 , +0.881741997,
    +0.949628649 , +0.983314592,
    +0.995517816 , +0.999160558,
    +0.999899195 , +0.999993155
]);

exports.CA = new Float32Array([
    -0.514495755, -0.471731969,
    -0.313377454, -0.181913200,
    -0.094574193, -0.040965583,
    -0.014198569, -0.003699975
]);

exports.COUNT1TABLE_SELECT = 0x01;
exports.SCALEFAC_SCALE     = 0x02;
exports.PREFLAG            = 0x04;
exports.MIXED_BLOCK_FLAG   = 0x08;

exports.I_STEREO  = 0x1;
exports.MS_STEREO = 0x2;

/*
 * windowing coefficients for long blocks
 * derived from section 2.4.3.4.10.3 of ISO/IEC 11172-3
 *
 * WINDOW_L[i] = sin((PI / 36) * (i + 1/2))
 */
exports.WINDOW_L = new Float32Array([
    0.043619387, 0.130526192,
    0.216439614, 0.300705800,
    0.382683432, 0.461748613,
    0.537299608, 0.608761429,
    0.675590208, 0.737277337,
    0.793353340, 0.843391446,

    0.887010833, 0.923879533,
    0.953716951, 0.976296007,
    0.991444861, 0.999048222,
    0.999048222, 0.991444861,
    0.976296007, 0.953716951,
    0.923879533, 0.887010833,

    0.843391446, 0.793353340,
    0.737277337, 0.675590208,
    0.608761429, 0.537299608,
    0.461748613, 0.382683432,
    0.300705800, 0.216439614,
    0.130526192, 0.043619387
]);

/*
 * windowing coefficients for short blocks
 * derived from section 2.4.3.4.10.3 of ISO/IEC 11172-3
 *
 * WINDOW_S[i] = sin((PI / 12) * (i + 1/2))
 */
exports.WINDOW_S = new Float32Array([
    0.130526192, 0.382683432,
    0.608761429, 0.793353340,
    0.923879533, 0.991444861,
    0.991444861, 0.923879533,
    0.793353340, 0.608761429,
    0.382683432, 0.130526192
]);

/*
 * coefficients for intensity stereo processing
 * derived from section 2.4.3.4.9.3 of ISO/IEC 11172-3
 *
 * is_ratio[i] = tan(i * (PI / 12))
 * IS_TABLE[i] = is_ratio[i] / (1 + is_ratio[i])
 */
exports.IS_TABLE = new Float32Array([
    0.000000000,
    0.211324865,
    0.366025404,
    0.500000000,
    0.633974596,
    0.788675135,
    1.000000000
]);

/*
 * coefficients for LSF intensity stereo processing
 * derived from section 2.4.3.2 of ISO/IEC 13818-3
 *
 * IS_LSF_TABLE[0][i] = (1 / sqrt(sqrt(2)))^(i + 1)
 * IS_LSF_TABLE[1][i] = (1 /      sqrt(2)) ^(i + 1)
 */
exports.IS_LSF_TABLE = [
    new Float32Array([
        0.840896415,
        0.707106781,
        0.594603558,
        0.500000000,
        0.420448208,
        0.353553391,
        0.297301779,
        0.250000000,
        0.210224104,
        0.176776695,
        0.148650889,
        0.125000000,
        0.105112052,
        0.088388348,
        0.074325445
    ]), 
    new Float32Array([
        0.707106781,
        0.500000000,
        0.353553391,
        0.250000000,
        0.176776695,
        0.125000000,
        0.088388348,
        0.062500000,
        0.044194174,
        0.031250000,
        0.022097087,
        0.015625000,
        0.011048543,
        0.007812500,
        0.005524272
    ])
];

/*
 * scalefactor bit lengths
 * derived from section 2.4.2.7 of ISO/IEC 11172-3
 */
exports.SFLEN_TABLE = [
    { slen1: 0, slen2: 0 }, { slen1: 0, slen2: 1 }, { slen1: 0, slen2: 2 }, { slen1: 0, slen2: 3 },
    { slen1: 3, slen2: 0 }, { slen1: 1, slen2: 1 }, { slen1: 1, slen2: 2 }, { slen1: 1, slen2: 3 },
    { slen1: 2, slen2: 1 }, { slen1: 2, slen2: 2 }, { slen1: 2, slen2: 3 }, { slen1: 3, slen2: 1 },
    { slen1: 3, slen2: 2 }, { slen1: 3, slen2: 3 }, { slen1: 4, slen2: 2 }, { slen1: 4, slen2: 3 }    
];

/*
 * number of LSF scalefactor band values
 * derived from section 2.4.3.2 of ISO/IEC 13818-3
 */
exports.NSFB_TABLE = [
    [ [  6,  5,  5, 5 ],
      [  9,  9,  9, 9 ],
      [  6,  9,  9, 9 ] ],

    [ [  6,  5,  7, 3 ],
      [  9,  9, 12, 6 ],
      [  6,  9, 12, 6 ] ],

    [ [ 11, 10,  0, 0 ],
      [ 18, 18,  0, 0 ],
      [ 15, 18,  0, 0 ] ],

    [ [  7,  7,  7, 0 ],
      [ 12, 12, 12, 0 ],
      [  6, 15, 12, 0 ] ],

    [ [  6,  6,  6, 3 ],
      [ 12,  9,  9, 6 ],
      [  6, 12,  9, 6 ] ],

    [ [  8,  8,  5, 0 ],
      [ 15, 12,  9, 0 ],
      [  6, 18,  9, 0 ] ]
];
 
},{}],15:[function(require,module,exports){
/**
 * Makes a multidimensional array
 */
exports.makeArray = function(lengths, Type) {
    if (!Type) Type = Float64Array;
    
    if (lengths.length === 1) {
        return new Type(lengths[0]);
    }
    
    var ret = [],
        len = lengths[0];
        
    for (var j = 0; j < len; j++) {
        ret[j] = exports.makeArray(lengths.slice(1), Type);
    }
    
    return ret;
};

},{}]},{},[1])
