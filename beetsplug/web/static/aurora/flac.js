(function e(t,n,r){function s(o,u){if(!n[o]){if(!t[o]){var a=typeof require=="function"&&require;if(!u&&a)return a(o,!0);if(i)return i(o,!0);throw new Error("Cannot find module '"+o+"'")}var f=n[o]={exports:{}};t[o][0].call(f.exports,function(e){var n=t[o][1][e];return s(n?n:e)},f,f.exports,e,t,n,r)}return n[o].exports}var i=typeof require=="function"&&require;for(var o=0;o<r.length;o++)s(r[o]);return s})({1:[function(require,module,exports){
exports.FLACDemuxer = require('./src/demuxer');
exports.FLACDecoder = require('./src/decoder');
require('./src/ogg');

},{"./src/decoder":2,"./src/demuxer":3,"./src/ogg":4}],2:[function(require,module,exports){
/*
 * FLAC.js - Free Lossless Audio Codec decoder in JavaScript
 * Original C version from FFmpeg (c) 2003 Alex Beregszaszi
 * JavaScript port by Devon Govett and Jens Nockert of Official.fm Labs
 * 
 * Licensed under the same terms as the original.  The original
 * license follows.
 *
 * FLAC.js is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * FLAC.js is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 */

var AV = (window.AV);

var FLACDecoder = AV.Decoder.extend(function() {
    AV.Decoder.register('flac', this);
    
    this.prototype.setCookie = function(cookie) {
        this.cookie = cookie;
        
        // initialize arrays
        this.decoded = [];
        for (var i = 0; i < this.format.channelsPerFrame; i++) {
            this.decoded[i] = new Int32Array(cookie.maxBlockSize);
        }
        
        // for 24 bit lpc frames, this is used to simulate a 64 bit int
        this.lpc_total = new Int32Array(2);
    };
    
    const BLOCK_SIZES = new Int16Array([
               0,      192, 576 << 0, 576 << 1, 576 << 2, 576 << 3,        0,        0,
        256 << 0, 256 << 1, 256 << 2, 256 << 3, 256 << 4, 256 << 5, 256 << 6, 256 << 7
    ]);
    
    const SAMPLE_RATES = new Int32Array([
        0, 88200, 176400, 192000,
        8000, 16000, 22050, 24000, 32000, 44100, 48000, 96000,
        0, 0, 0, 0
    ]);
    
    const SAMPLE_SIZES = new Int8Array([
        0, 8, 12, 0, 16, 20, 24, 0
    ]);
    
    const MAX_CHANNELS = 8,
          CHMODE_INDEPENDENT = 0,
          CHMODE_LEFT_SIDE = 8,
          CHMODE_RIGHT_SIDE = 9,
          CHMODE_MID_SIDE = 10;
    
    this.prototype.readChunk = function() {
        var stream = this.bitstream;
        if (!stream.available(32))
            return;
                            
        // frame sync code
        if ((stream.read(15) & 0x7FFF) !== 0x7FFC)
            throw new Error('Invalid sync code');
            
        var isVarSize = stream.read(1),  // variable block size stream code
            bsCode = stream.read(4),  // block size
            srCode = stream.read(4),  // sample rate code
            chMode = stream.read(4),  // channel mode
            bpsCode = stream.read(3); // bits per sample
            
        stream.advance(1); // reserved bit
        
        // channels
        this.chMode = chMode;
        var channels;
        
        if (chMode < MAX_CHANNELS) {
            channels = chMode + 1;
            this.chMode = CHMODE_INDEPENDENT;
        } else if (chMode <= CHMODE_MID_SIDE) {
            channels = 2;
        } else {
            throw new Error('Invalid channel mode');
        }
        
        if (channels !== this.format.channelsPerFrame)
            throw new Error('Switching channel layout mid-stream not supported.');
        
        // bits per sample    
        if (bpsCode === 3 || bpsCode === 7)
            throw new Error('Invalid sample size code');
            
        this.bps = SAMPLE_SIZES[bpsCode];
        if (this.bps !== this.format.bitsPerChannel)
            throw new Error('Switching bits per sample mid-stream not supported.');
        
        // sample number or frame number
        // see http://www.hydrogenaudio.org/forums/index.php?s=ea7085ffe6d57132c36e6105c0d434c9&showtopic=88390&pid=754269&st=0&#entry754269
        var ones = 0;
        while (stream.read(1) === 1)
            ones++;
        
        var frame_or_sample_num = stream.read(7 - ones);
        for (; ones > 1; ones--) {
            stream.advance(2); // == 2
            frame_or_sample_num = (frame_or_sample_num << 6) | stream.read(6);
        }
                
        // block size
        if (bsCode === 0)
            throw new Error('Reserved blocksize code');
        else if (bsCode === 6)
            this.blockSize = stream.read(8) + 1;
        else if (bsCode === 7)
            this.blockSize = stream.read(16) + 1;
        else
            this.blockSize = BLOCK_SIZES[bsCode];
            
        // sample rate
        var sampleRate;
        if (srCode < 12)
            sampleRate = SAMPLE_RATES[srCode];
        else if (srCode === 12)
            sampleRate = stream.read(8) * 1000;
        else if (srCode === 13)
            sampleRate = stream.read(16);
        else if (srCode === 14)
            sampleRate = stream.read(16) * 10;
        else
            throw new Error('Invalid sample rate code');
            
        stream.advance(8); // skip CRC check
        
        // subframes
        for (var i = 0; i < channels; i++)
            this.decodeSubframe(i);
        
        stream.align();
        stream.advance(16); // skip CRC frame footer
        
        var is32 = this.bps > 16,
            output = new ArrayBuffer(this.blockSize * channels * (is32 ? 4 : 2)),
            buf = is32 ? new Int32Array(output) : new Int16Array(output),
            blockSize = this.blockSize,
            decoded = this.decoded,
            j = 0;
            
        switch (this.chMode) {
            case CHMODE_INDEPENDENT:
                for (var k = 0; k < blockSize; k++) {
                    for (var i = 0; i < channels; i++) {
                        buf[j++] = decoded[i][k];
                    }
                }
                break;
                
            case CHMODE_LEFT_SIDE:
                for (var i = 0; i < blockSize; i++) {
                    var left = decoded[0][i],
                        right = decoded[1][i];

                    buf[j++] = left;
                    buf[j++] = (left - right);
                }
                break;
                
            case CHMODE_RIGHT_SIDE:
                for (var i = 0; i < blockSize; i++) {
                    var left = decoded[0][i],
                        right = decoded[1][i];

                    buf[j++] = (left + right);
                    buf[j++] = right;
                }
                break;
                
            case CHMODE_MID_SIDE:
                for (var i = 0; i < blockSize; i++) {
                    var left = decoded[0][i],
                        right = decoded[1][i];
                    
                    left -= right >> 1;
                    buf[j++] = (left + right);
                    buf[j++] = left;
                }
                break;
        }
        
        return buf;
    };
    
    this.prototype.decodeSubframe = function(channel) {
        var wasted = 0,
            stream = this.bitstream,
            blockSize = this.blockSize,
            decoded = this.decoded;
        
        this.curr_bps = this.bps;
        if (channel === 0) {
            if (this.chMode === CHMODE_RIGHT_SIDE)
                this.curr_bps++;
        } else {
            if (this.chMode === CHMODE_LEFT_SIDE || this.chMode === CHMODE_MID_SIDE)
                this.curr_bps++;
        }
        
        if (stream.read(1))
            throw new Error("Invalid subframe padding");
        
        var type = stream.read(6);
        
        if (stream.read(1)) {
            wasted = 1;
            while (!stream.read(1))
                wasted++;

            this.curr_bps -= wasted;
        }
        
        if (this.curr_bps > 32)
            throw new Error("decorrelated bit depth > 32 (" + this.curr_bps + ")");
        
        if (type === 0) {
            var tmp = stream.read(this.curr_bps, true);
            for (var i = 0; i < blockSize; i++)
                decoded[channel][i] = tmp;
                
        } else if (type === 1) {
            var bps = this.curr_bps;
            for (var i = 0; i < blockSize; i++)
                decoded[channel][i] = stream.read(bps, true);
                
        } else if ((type >= 8) && (type <= 12)) {
            this.decode_subframe_fixed(channel, type & ~0x8);
                
        } else if (type >= 32) {
            this.decode_subframe_lpc(channel, (type & ~0x20) + 1);

        } else {
            throw new Error("Invalid coding type");
        }
        
        if (wasted) {
            for (var i = 0; i < blockSize; i++)
                decoded[channel][i] <<= wasted;
        }
    };
    
    this.prototype.decode_subframe_fixed = function(channel, predictor_order) {
        var decoded = this.decoded[channel],
            stream = this.bitstream,
            bps = this.curr_bps;
    
        // warm up samples
        for (var i = 0; i < predictor_order; i++)
            decoded[i] = stream.read(bps, true);
    
        this.decode_residuals(channel, predictor_order);
        
        var a = 0, b = 0, c = 0, d = 0;
        
        if (predictor_order > 0) 
            a = decoded[predictor_order - 1];
        
        if (predictor_order > 1)
            b = a - decoded[predictor_order - 2];
        
        if (predictor_order > 2) 
            c = b - decoded[predictor_order - 2] + decoded[predictor_order - 3];
        
        if (predictor_order > 3)
            d = c - decoded[predictor_order - 2] + 2 * decoded[predictor_order - 3] - decoded[predictor_order - 4];
            
        switch (predictor_order) {
            case 0:
                break;
                
            case 1:
            case 2:
            case 3:
            case 4:
                var abcd = new Int32Array([a, b, c, d]),
                    blockSize = this.blockSize;
                    
                for (var i = predictor_order; i < blockSize; i++) {
                    abcd[predictor_order - 1] += decoded[i];
                    
                    for (var j = predictor_order - 2; j >= 0; j--) {
                        abcd[j] += abcd[j + 1];
                    }
                    
                    decoded[i] = abcd[0];
                }
                
                break;
                
            default:
                throw new Error("Invalid Predictor Order " + predictor_order);
        }
    };
    
    this.prototype.decode_subframe_lpc = function(channel, predictor_order) {
        var stream = this.bitstream,
            decoded = this.decoded[channel],
            bps = this.curr_bps,
            blockSize = this.blockSize;
            
        // warm up samples
        for (var i = 0; i < predictor_order; i++) {
            decoded[i] = stream.read(bps, true);
        }

        var coeff_prec = stream.read(4) + 1;
        if (coeff_prec === 16)
            throw new Error("Invalid coefficient precision");
        
        var qlevel = stream.read(5, true);
        if (qlevel < 0)
            throw new Error("Negative qlevel, maybe buggy stream");
        
        var coeffs = new Int32Array(32);
        for (var i = 0; i < predictor_order; i++) {
            coeffs[i] = stream.read(coeff_prec, true);
        }
        
        this.decode_residuals(channel, predictor_order);
        
        if (this.bps <= 16) {
            for (var i = predictor_order; i < blockSize - 1; i += 2) {
                var d = decoded[i - predictor_order],
                    s0 = 0, s1 = 0, c = 0;
            
                for (var j = predictor_order - 1; j > 0; j--) {
                    c = coeffs[j];
                    s0 += c * d;
                    d = decoded[i - j];
                    s1 += c * d;
                }
            
                c = coeffs[0];
                s0 += c * d;
                d = decoded[i] += (s0 >> qlevel);
                s1 += c * d;
                decoded[i + 1] += (s1 >> qlevel);
            }
            
            if (i < blockSize) {
                var sum = 0;
                for (var j = 0; j < predictor_order; j++)
                    sum += coeffs[j] * decoded[i - j - 1];
            
                decoded[i] += (sum >> qlevel);
            }
        } else {
            // simulate 64 bit integer using an array of two 32 bit ints
            var total = this.lpc_total;
            for (var i = predictor_order; i < blockSize; i++) {
                // reset total to 0
                total[0] = 0;
                total[1] = 0;

                for (j = 0; j < predictor_order; j++) {
                    // simulate `total += coeffs[j] * decoded[i - j - 1]`
                    multiply_add(total, coeffs[j], decoded[i - j - 1]);                    
                }

                // simulate `decoded[i] += total >> qlevel`
                // we know that qlevel < 32 since it is a 5 bit field (see above)
                decoded[i] += (total[0] >>> qlevel) | (total[1] << (32 - qlevel));
            }
        }
    };
    
    const TWO_PWR_32_DBL = Math.pow(2, 32);
        
    // performs `total += a * b` on a simulated 64 bit int
    // total is an Int32Array(2)
    // a and b are JS numbers (32 bit ints)
    function multiply_add(total, a, b) {
        // multiply a * b (we can use normal JS multiplication for this)
        var r = a * b;
        var n = r < 0;
        if (n)
            r = -r;
            
        var r_low = (r % TWO_PWR_32_DBL) | 0;
        var r_high = (r / TWO_PWR_32_DBL) | 0;
        if (n) {
            r_low = ~r_low + 1;
            r_high = ~r_high;
        }
        
        // add result to total
        var a48 = total[1] >>> 16;
        var a32 = total[1] & 0xFFFF;
        var a16 = total[0] >>> 16;
        var a00 = total[0] & 0xFFFF;

        var b48 = r_high >>> 16;
        var b32 = r_high & 0xFFFF;
        var b16 = r_low >>> 16;
        var b00 = r_low & 0xFFFF;

        var c48 = 0, c32 = 0, c16 = 0, c00 = 0;
        c00 += a00 + b00;
        c16 += c00 >>> 16;
        c00 &= 0xFFFF;
        c16 += a16 + b16;
        c32 += c16 >>> 16;
        c16 &= 0xFFFF;
        c32 += a32 + b32;
        c48 += c32 >>> 16;
        c32 &= 0xFFFF;
        c48 += a48 + b48;
        c48 &= 0xFFFF;
        
        // store result back in total
        total[0] = (c16 << 16) | c00;
        total[1] = (c48 << 16) | c32;
    }
     
    const INT_MAX = 32767;
    
    this.prototype.decode_residuals = function(channel, predictor_order) {
        var stream = this.bitstream,
            method_type = stream.read(2);
            
        if (method_type > 1)
            throw new Error('Illegal residual coding method ' + method_type);
        
        var rice_order = stream.read(4),
            samples = (this.blockSize >>> rice_order);
            
        if (predictor_order > samples)
            throw new Error('Invalid predictor order ' + predictor_order + ' > ' + samples);
        
        var decoded = this.decoded[channel],
            sample = predictor_order, 
            i = predictor_order;
        
        for (var partition = 0; partition < (1 << rice_order); partition++) {
            var tmp = stream.read(method_type === 0 ? 4 : 5);

            if (tmp === (method_type === 0 ? 15 : 31)) {
                tmp = stream.read(5);
                for (; i < samples; i++)
                    decoded[sample++] = stream.read(tmp, true);
                    
            } else {
                for (; i < samples; i++)
                    decoded[sample++] = this.golomb(tmp, INT_MAX, 0);
            }
            
            i = 0;
        }
    };
    
    const MIN_CACHE_BITS = 25;
    
    this.prototype.golomb = function(k, limit, esc_len) {
        var data = this.bitstream,
            offset = data.bitPosition,
            buf = data.peek(32 - offset) << offset,
            v = 0;
        
        var log = 31 - clz(buf | 1); // log2(buf)

        if (log - k >= 32 - MIN_CACHE_BITS && 32 - log < limit) {
            buf >>>= log - k;
            buf += (30 - log) << k;

            data.advance(32 + k - log);
            v = buf;
            
        } else {
            for (var i = 0; data.read(1) === 0; i++)
                buf = data.peek(32 - offset) << offset;

            if (i < limit - 1) {
                if (k)
                    buf = data.read(k);
                else
                    buf = 0;

                v = buf + (i << k);
                
            } else if (i === limit - 1) {
                buf = data.read(esc_len);
                v = buf + 1;
                
            } else {
                v = -1;
            }
        }
        
        return (v >> 1) ^ -(v & 1);
    };
    
    // Should be in the damned standard library...
    function clz(input) {
        var output = 0,
            curbyte = 0;

        while(true) { // emulate goto in JS using the break statement :D
            curbyte = input >>> 24;
            if (curbyte) break;
            output += 8;

            curbyte = input >>> 16;
            if (curbyte & 0xff) break;
            output += 8;

            curbyte = input >>> 8;
            if (curbyte & 0xff) break;
            output += 8;

            curbyte = input;
            if (curbyte & 0xff) break;
            output += 8;

            return output;
        }

        if (!(curbyte & 0xf0))
            output += 4;
        else
            curbyte >>>= 4;

        if (curbyte & 0x8)
            return output;
            
        if (curbyte & 0x4)
            return output + 1;
            
        if (curbyte & 0x2)
            return output + 2;
            
        if (curbyte & 0x1)
            return output + 3;

        // shouldn't get here
        return output + 4;
    }
});

module.exports = FLACDecoder;

},{}],3:[function(require,module,exports){
/*
 * FLAC.js - Free Lossless Audio Codec decoder in JavaScript
 * By Devon Govett and Jens Nockert of Official.fm Labs
 *
 * FLAC.js is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * FLAC.js is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 */

var AV = (window.AV);

var FLACDemuxer = AV.Demuxer.extend(function() {
    AV.Demuxer.register(this);
    
    this.probe = function(buffer) {
        return buffer.peekString(0, 4) === 'fLaC';
    }
    
    const STREAMINFO = 0,
          PADDING = 1,
          APPLICATION = 2,
          SEEKTABLE = 3,
          VORBIS_COMMENT = 4,
          CUESHEET = 5,
          PICTURE = 6,
          INVALID = 127,
          STREAMINFO_SIZE = 34;
    
    this.prototype.readChunk = function() {
        var stream = this.stream;
        
        if (!this.readHeader && stream.available(4)) {
            if (stream.readString(4) !== 'fLaC')
                return this.emit('error', 'Invalid FLAC file.');
                
            this.readHeader = true;
        }
        
        while (stream.available(1) && !this.last) {                     
            if (!this.readBlockHeaders) {
                var tmp = stream.readUInt8();
                this.last = (tmp & 0x80) === 0x80,
                this.type = tmp & 0x7F,
                this.size = stream.readUInt24();
            }
            
            if (!this.foundStreamInfo && this.type !== STREAMINFO)
                return this.emit('error', 'STREAMINFO must be the first block');
                
            if (!stream.available(this.size))
                return;
            
            switch (this.type) {
                case STREAMINFO:
                    if (this.foundStreamInfo)
                        return this.emit('error', 'STREAMINFO can only occur once.');
                    
                    if (this.size !== STREAMINFO_SIZE)
                        return this.emit('error', 'STREAMINFO size is wrong.');
                    
                    this.foundStreamInfo = true;
                    var bitstream = new AV.Bitstream(stream);
                
                    var cookie = {
                        minBlockSize: bitstream.read(16),
                        maxBlockSize: bitstream.read(16),
                        minFrameSize: bitstream.read(24),
                        maxFrameSize: bitstream.read(24)
                    };
                
                    this.format = {
                        formatID: 'flac',
                        sampleRate: bitstream.read(20),
                        channelsPerFrame: bitstream.read(3) + 1,
                        bitsPerChannel: bitstream.read(5) + 1
                    };
                
                    this.emit('format', this.format);
                    this.emit('cookie', cookie);
                
                    var sampleCount = bitstream.read(36);
                    this.emit('duration', sampleCount / this.format.sampleRate * 1000 | 0);
                
                    stream.advance(16); // skip MD5 hashes
                    this.readBlockHeaders = false;
                    break;

                    /*
                    I am only looking at the least significant 32 bits of sample number and offset data
                    This is more than sufficient for the longest flac file I have (~50 mins 2-channel 16-bit 44.1k which uses about 7.5% of the UInt32 space for the largest offset)
                    Can certainly be improved by storing sample numbers and offests as doubles, but would require additional overriding of the searchTimestamp and seek functions (possibly more?)
                    Also the flac faq suggests it would be possible to find frame lengths and thus create seek points on the fly via decoding but I assume this would be slow
                    I may look into these thigns though as my project progresses
                    */
                    case SEEKTABLE:
                        for(var s=0; s<this.size/18; s++)
                        {
                            if(stream.peekUInt32(0) == 0xFFFFFFFF && stream.peekUInt32(1) == 0xFFFFFFFF)
                            {
                                //placeholder, ignore
                                stream.advance(18);
                            } else {
                                if(stream.readUInt32() > 0)
                                {
                                    this.emit('error', 'Seek points with sample number >UInt32 not supported');
                                }
                                var samplenum = stream.readUInt32();
                                if(stream.readUInt32() > 0)
                                {
                                    this.emit('error', 'Seek points with stream offset >UInt32 not supported');
                                }
                                var offset = stream.readUInt32();

                                stream.advance(2);

                                this.addSeekPoint(offset, samplenum);
                            }
                        }
                        break;

                case VORBIS_COMMENT:
                    // see http://www.xiph.org/vorbis/doc/v-comment.html
                    this.metadata || (this.metadata = {});
                    var len = stream.readUInt32(true);
                    
                    this.metadata.vendor = stream.readString(len);
                    var length = stream.readUInt32(true);
                    
                    for (var i = 0; i < length; i++) {
                        len = stream.readUInt32(true);
                        var str = stream.readString(len, 'utf8'),
                            idx = str.indexOf('=');
                            
                        this.metadata[str.slice(0, idx).toLowerCase()] = str.slice(idx + 1);
                    }
                    
                    // TODO: standardize field names across formats
                    break;
                    
                case PICTURE:
                    var type = stream.readUInt32();
                    if (type !== 3) { // make sure this is album art (type 3)
                        stream.advance(this.size - 4);
                    } else {
                        var mimeLen = stream.readUInt32(),
                            mime = stream.readString(mimeLen),
                            descLen = stream.readUInt32(),
                            description = stream.readString(descLen),
                            width = stream.readUInt32(),
                            height = stream.readUInt32(),
                            depth = stream.readUInt32(),
                            colors = stream.readUInt32(),
                            length = stream.readUInt32(),
                            picture = stream.readBuffer(length);
                    
                        this.metadata || (this.metadata = {});
                        this.metadata.coverArt = picture;
                    }
                    
                    // does anyone want the rest of the info?
                    break;
                
                default:
                    stream.advance(this.size);
                    this.readBlockHeaders = false;
            }
            
            if (this.last && this.metadata)
                this.emit('metadata', this.metadata);
        }
        
        while (stream.available(1) && this.last) {
            var buffer = stream.readSingleBuffer(stream.remainingBytes());
            this.emit('data', buffer);
        }
    }
    
});

module.exports = FLACDemuxer;

},{}],4:[function(require,module,exports){
var AV = (window.AV);

// if ogg.js exists, register a plugin
try {
  var OggDemuxer = (window.AV.OggDemuxer);
} catch (e) {};
if (!OggDemuxer) return;

OggDemuxer.plugins.push({
  magic: "\177FLAC",
  
  init: function() {
    this.list = new AV.BufferList();
    this.stream = new AV.Stream(this.list);
  },
  
  readHeaders: function(packet) {
    var stream = this.stream;
    this.list.append(new AV.Buffer(packet));
    
    stream.advance(5); // magic
    if (stream.readUInt8() != 1)
      throw new Error('Unsupported FLAC version');
      
    stream.advance(3);
    if (stream.peekString(0, 4) != 'fLaC')
      throw new Error('Not flac');
      
    this.flac = AV.Demuxer.find(stream.peekSingleBuffer(0, stream.remainingBytes()));
    if (!this.flac)
      throw new Error('Flac demuxer not found');
    
    this.flac.prototype.readChunk.call(this);
    return true;
  },
  
  readPacket: function(packet) {
    this.list.append(new AV.Buffer(packet));
    this.flac.prototype.readChunk.call(this);
  }
});

},{}]},{},[1])
