import xml.etree.ElementTree as ET
import string
import StringIO
import logging
try:
	from ET import fixtag
except:
	# Python < 2.7
	def fixtag(tag, namespaces):
		# given a decorated tag (of the form {uri}tag), return prefixed
		# tag and namespace declaration, if any
		if isinstance(tag, ET.QName):
			tag = tag.text
		namespace_uri, tag = string.split(tag[1:], "}", 1)
		prefix = namespaces.get(namespace_uri)
		if prefix is None:
			prefix = "ns%d" % len(namespaces)
			namespaces[namespace_uri] = prefix
			if prefix == "xml":
				xmlns = None
			else:
				xmlns = ("xmlns:%s" % prefix, namespace_uri)
		else:
			xmlns = None
		return "%s:%s" % (prefix, tag), xmlns

NS_MAP = {"http://musicbrainz.org/ns/mmd-2.0#": "ws2"}
_log = logging.getLogger("python-musicbrainz-ngs")

def make_artist_credit(artists):
	names = []
	for artist in artists:
		if isinstance(artist, dict):
			names.append(artist.get("artist", {}).get("name", ""))
		else:
			names.append(artist)
	return "".join(names)

def parse_elements(valid_els, element):
	""" Extract single level subelements from an element.
	    For example, given the element:
	    <element>
	        <subelement>Text</subelement>
	    </element>
	    and a list valid_els that contains "subelement",
	    return a dict {'subelement': 'Text'}
	"""
	result = {}
	for sub in element:
		t = fixtag(sub.tag, NS_MAP)[0]
		if ":" in t:
			t = t.split(":")[1]
		if t in valid_els:
			result[t] = sub.text
		else:
			_log.debug("in <%s>, uncaught <%s>", fixtag(element.tag, NS_MAP)[0], t)
	return result

def parse_attributes(attributes, element):
	""" Extract attributes from an element.
	    For example, given the element:
	    <element type="Group" />
	    and a list attributes that contains "type",
	    return a dict {'type': 'Group'}
	"""
	result = {}
	for attr in attributes:
		if attr in element.attrib:
			result[attr] = element.attrib[attr]
		else:
			_log.debug("in <%s>, uncaught attribute %s", fixtag(element.tag, NS_MAP)[0], attr)
	return result

def parse_inner(inner_els, element):
	""" Delegate the parsing of a subelement to another function.
	    For example, given the element:
	    <element>
	        <subelement>
	            <a>Foo</a><b>Bar</b>
		</subelement>
	    </element>
	    and a dictionary {'subelement': parse_subelement},
	    call parse_subelement(<subelement>) and
	    return a dict {'subelement': <result>}
	    if parse_subelement returns a tuple of the form
	    ('subelement-key', <result>) then return a dict
	    {'subelement-key': <result>} instead
	"""
	result = {}
	for sub in element:
		t = fixtag(sub.tag, NS_MAP)[0]
		if ":" in t:
			t = t.split(":")[1]
		if t in inner_els.keys():
			inner_result = inner_els[t](sub)
			if isinstance(inner_result, tuple):
				result[inner_result[0]] = inner_result[1]
			else:
				result[t] = inner_result
		else:
			_log.debug("in <%s>, not delegating <%s>", fixtag(element.tag, NS_MAP)[0], t)
	return result

def parse_message(message):
	s = message.read()
	f = StringIO.StringIO(s)
	tree = ET.ElementTree(file=f)
	root = tree.getroot()
	result = {}
	valid_elements = {"artist": parse_artist,
	                  "label": parse_label,
	                  "release": parse_release,
	                  "release-group": parse_release_group,
	                  "recording": parse_recording,
	                  "work": parse_work,

	                  "disc": parse_disc,
	                  "puid": parse_puid,
	                  "echoprint": parse_puid,

	                  "artist-list": parse_artist_list,
	                  "label-list": parse_label_list,
	                  "release-list": parse_release_list,
	                  "release-group-list": parse_release_group_list,
	                  "recording-list": parse_recording_list,
	                  "work-list": parse_work_list,
	
	                  "collection-list": parse_collection_list,
	                  "collection": parse_collection,

	                  "message": parse_response_message
	                  }
	result.update(parse_inner(valid_elements, root))
	return result

def parse_response_message(message):
    return parse_elements(["text"], message)

def parse_collection_list(cl):
	return [parse_collection(c) for c in cl]

def parse_collection(collection):
	result = {}
	attribs = ["id"]
	elements = ["name", "editor"]
	inner_els = {"release-list": parse_release_list}
	result.update(parse_attributes(attribs, collection))
	result.update(parse_elements(elements, collection))
	result.update(parse_inner(inner_els, collection))

	return result

def parse_collection_release_list(rl):
	attribs = ["count"]
	return parse_attributes(attribs, rl)

def parse_artist_lifespan(lifespan):
	parts = parse_elements(["begin", "end"], lifespan)

	return parts

def parse_artist_list(al):
	return [parse_artist(a) for a in al]

def parse_artist(artist):
	result = {}
	attribs = ["id", "type"]
	elements = ["name", "sort-name", "country", "user-rating"]
	inner_els = {"life-span": parse_artist_lifespan,
	             "recording-list": parse_recording_list,
	             "release-list": parse_release_list,
	             "release-group-list": parse_release_group_list,
	             "work-list": parse_work_list,
	             "tag-list": parse_tag_list,
	             "user-tag-list": parse_tag_list,
	             "rating": parse_rating,
	             "alias-list": parse_alias_list}

	result.update(parse_attributes(attribs, artist))
	result.update(parse_elements(elements, artist))
	result.update(parse_inner(inner_els, artist))

	return result

def parse_label_list(ll):
	return [parse_label(l) for l in ll]

def parse_label(label):
	result = {}
	attribs = ["id", "type"]
	elements = ["name", "sort-name", "country", "label-code", "user-rating"]
	inner_els = {"life-span": parse_artist_lifespan,
	             "release-list": parse_release_list,
	             "tag-list": parse_tag_list,
	             "user-tag-list": parse_tag_list,
	             "rating": parse_rating,
	             "alias-list": parse_alias_list}

	result.update(parse_attributes(attribs, label))
	result.update(parse_elements(elements, label))
	result.update(parse_inner(inner_els, label))

	return result

def parse_attribute_list(al):
    return [parse_attribute_tag(a) for a in al]

def parse_attribute_tag(attribute):
    return attribute.text

def parse_relation_list(rl):
    attribs = ["target-type"]
    ttype = parse_attributes(attribs, rl)
    key = "%s-relation-list" % ttype["target-type"]
    return (key, [parse_relation(r) for r in rl])

def parse_relation(relation):
    result = {}
    attribs = ["type"]
    elements = ["target", "direction"]
    inner_els = {"artist": parse_artist,
                 "label": parse_label,
                 "recording": parse_recording,
                 "release": parse_release,
                 "release-group": parse_release_group,
                 "attribute-list": parse_attribute_list,
                 "work": parse_work
                }
    result.update(parse_attributes(attribs, relation))
    result.update(parse_elements(elements, relation))
    result.update(parse_inner(inner_els, relation))

    return result

def parse_release(release):
	result = {}
	attribs = ["id"]
	elements = ["title", "status", "disambiguation", "quality", "country", "barcode", "date", "packaging", "asin"]
	inner_els = {"text-representation": parse_text_representation,
	             "artist-credit": parse_artist_credit,
	             "label-info-list": parse_label_info_list,
	             "medium-list": parse_medium_list,
	             "release-group": parse_release_group,
	             "relation-list": parse_relation_list}

	result.update(parse_attributes(attribs, release))
	result.update(parse_elements(elements, release))
	result.update(parse_inner(inner_els, release))
	if "artist-credit" in result:
		result["artist-credit-phrase"] = make_artist_credit(result["artist-credit"])

	return result

def parse_medium_list(ml):
	return [parse_medium(m) for m in ml]

def parse_medium(medium):
	result = {}
	elements = ["position", "format", "title"]
	inner_els = {"disc-list": parse_disc_list,
	             "track-list": parse_track_list}

	result.update(parse_elements(elements, medium))
	result.update(parse_inner(inner_els, medium))
	return result

def parse_disc_list(dl):
	return [parse_disc(d) for d in dl]

def parse_text_representation(textr):
	return parse_elements(["language", "script"], textr)

def parse_release_group(rg):
	result = {}
	attribs = ["id", "type"]
	elements = ["title", "user-rating", "first-release-date"]
	inner_els = {"artist-credit": parse_artist_credit,
	             "release-list": parse_release_list,
	             "tag-list": parse_tag_list,
	             "user-tag-list": parse_tag_list,
	             "rating": parse_rating}

	result.update(parse_attributes(attribs, rg))
	result.update(parse_elements(elements, rg))
	result.update(parse_inner(inner_els, rg))
	if "artist-credit" in result:
		result["artist-credit-phrase"] = make_artist_credit(result["artist-credit"])

	return result

def parse_recording(recording):
	result = {}
	attribs = ["id"]
	elements = ["title", "length", "user-rating"]
	inner_els = {"artist-credit": parse_artist_credit,
	             "release-list": parse_release_list,
	             "tag-list": parse_tag_list,
	             "user-tag-list": parse_tag_list,
	             "rating": parse_rating,
	             "puid-list": parse_external_id_list,
	             "isrc-list": parse_external_id_list,
	             "echoprint-list": parse_external_id_list}

	result.update(parse_attributes(attribs, recording))
	result.update(parse_elements(elements, recording))
	result.update(parse_inner(inner_els, recording))
	if "artist-credit" in result:
		result["artist-credit-phrase"] = make_artist_credit(result["artist-credit"])

	return result

def parse_external_id_list(pl):
	return [parse_attributes(["id"], p)["id"] for p in pl]

def parse_work_list(wl):
	result = []
	for w in wl:
		result.append(parse_work(w))
	return result

def parse_work(work):
	result = {}
	attribs = ["id"]
	elements = ["title", "user-rating"]
	inner_els = {"tag-list": parse_tag_list,
	             "user-tag-list": parse_tag_list,
	             "rating": parse_rating,
	             "alias-list": parse_alias_list}

	result.update(parse_attributes(attribs, work))
	result.update(parse_elements(elements, work))
	result.update(parse_inner(inner_els, work))

	return result

def parse_disc(disc):
	result = {}
	attribs = ["id"]
	elements = ["sectors"]
	inner_els = {"release-list": parse_release_list}

	result.update(parse_attributes(attribs, disc))
	result.update(parse_elements(elements, disc))
	result.update(parse_inner(inner_els, disc))

	return result

def parse_release_list(rl):
	result = []
	for r in rl:
		result.append(parse_release(r))
	return result

def parse_release_group_list(rgl):
	result = []
	for rg in rgl:
		result.append(parse_release_group(rg))
	return result

def parse_puid(puid):
	result = {}
	attribs = ["id"]
	inner_els = {"recording-list": parse_recording_list}

	result.update(parse_attributes(attribs, puid))
	result.update(parse_inner(inner_els, puid))

	return result

def parse_recording_list(recs):
	result = []
	for r in recs:
		result.append(parse_recording(r))
	return result

def parse_artist_credit(ac):
	result = []
	for namecredit in ac:
		result.append(parse_name_credit(namecredit))
		join = parse_attributes(["joinphrase"], namecredit)
		if "joinphrase" in join:
			result.append(join["joinphrase"])
	return result

def parse_name_credit(nc):
	result = {}
	elements = ["name"]
	inner_els = {"artist": parse_artist}

	result.update(parse_elements(elements, nc))
	result.update(parse_inner(inner_els, nc))

	return result

def parse_label_info_list(lil):
	result = []

	for li in lil:
		result.append(parse_label_info(li))
	return result

def parse_label_info(li):
	result = {}
	elements = ["catalog-number"]
	inner_els = {"label": parse_label}

	result.update(parse_elements(elements, li))
	result.update(parse_inner(inner_els, li))
	return result

def parse_track_list(tl):
	result = []
	for t in tl:
		result.append(parse_track(t))
	return result

def parse_track(track):
	result = {}
	elements = ["position", "title"]
	inner_els = {"recording": parse_recording}

	result.update(parse_elements(elements, track))
	result.update(parse_inner(inner_els, track))
	return result

def parse_tag_list(tl):
	result = []
	for t in tl:
		result.append(parse_tag(t))
	return result

def parse_tag(tag):
	result = {}
	attribs = ["count"]
	elements = ["name"]

	result.update(parse_attributes(attribs, tag))
	result.update(parse_elements(elements, tag))

	return result

def parse_rating(rating):
	result = {}
	attribs = ["votes-count"]

	result.update(parse_attributes(attribs, rating))
	result["rating"] = rating.text

	return result

def parse_alias_list(al):
	result = []
	for a in al:
		result.append(a.text)
	return result

###
def make_barcode_request(barcodes):
	NS = "http://musicbrainz.org/ns/mmd-2.0#"
	root = ET.Element("{%s}metadata" % NS)
	rel_list = ET.SubElement(root, "{%s}release-list" % NS)
	for release, barcode in barcodes.items():
		rel_xml = ET.SubElement(rel_list, "{%s}release" % NS)
		bar_xml = ET.SubElement(rel_xml, "{%s}barcode" % NS)
		rel_xml.set("{%s}id" % NS, release)
		bar_xml.text = barcode

	return ET.tostring(root, "utf-8")

def make_puid_request(puids):
	NS = "http://musicbrainz.org/ns/mmd-2.0#"
	root = ET.Element("{%s}metadata" % NS)
	rec_list = ET.SubElement(root, "{%s}recording-list" % NS)
	for recording, puid_list in puids.items():
		rec_xml = ET.SubElement(rec_list, "{%s}recording" % NS)
		rec_xml.set("id", recording)
		p_list_xml = ET.SubElement(rec_xml, "{%s}puid-list" % NS)
		l = puid_list if isinstance(puid_list, list) else [puid_list]
		for p in l:
			p_xml = ET.SubElement(p_list_xml, "{%s}puid" % NS)
			p_xml.set("id", p)

	return ET.tostring(root, "utf-8")

def make_echoprint_request(echoprints):
	NS = "http://musicbrainz.org/ns/mmd-2.0#"
	root = ET.Element("{%s}metadata" % NS)
	rec_list = ET.SubElement(root, "{%s}recording-list" % NS)
	for recording, echoprint_list in echoprints.items():
		rec_xml = ET.SubElement(rec_list, "{%s}recording" % NS)
		rec_xml.set("id", recording)
		e_list_xml = ET.SubElement(rec_xml, "{%s}echoprint-list" % NS)
		l = echoprint_list if isinstance(echoprint_list, list) else [echoprint_list]
		for e in l:
			e_xml = ET.SubElement(e_list_xml, "{%s}echoprint" % NS)
			e_xml.set("id", e)

	return ET.tostring(root, "utf-8")

def make_tag_request(artist_tags, recording_tags):
	NS = "http://musicbrainz.org/ns/mmd-2.0#"
	root = ET.Element("{%s}metadata" % NS)
	rec_list = ET.SubElement(root, "{%s}recording-list" % NS)
	for rec, tags in recording_tags.items():
		rec_xml = ET.SubElement(rec_list, "{%s}recording" % NS)
		rec_xml.set("{%s}id" % NS, rec)
		taglist = ET.SubElement(rec_xml, "{%s}user-tag-list" % NS)
		for t in tags:
			usertag_xml = ET.SubElement(taglist, "{%s}user-tag" % NS)
			name_xml = ET.SubElement(usertag_xml, "{%s}name" % NS)
			name_xml.text = t
	art_list = ET.SubElement(root, "{%s}artist-list" % NS)
	for art, tags in artist_tags.items():
		art_xml = ET.SubElement(art_list, "{%s}artist" % NS)
		art_xml.set("{%s}id" % NS, art)
		taglist = ET.SubElement(art_xml, "{%s}user-tag-list" % NS)
		for t in tags:
			usertag_xml = ET.SubElement(taglist, "{%s}user-tag" % NS)
			name_xml = ET.SubElement(usertag_xml, "{%s}name" % NS)
			name_xml.text = t

	return ET.tostring(root, "utf-8")

def make_rating_request(artist_ratings, recording_ratings):
	NS = "http://musicbrainz.org/ns/mmd-2.0#"
	root = ET.Element("{%s}metadata" % NS)
	rec_list = ET.SubElement(root, "{%s}recording-list" % NS)
	for rec, rating in recording_ratings.items():
		rec_xml = ET.SubElement(rec_list, "{%s}recording" % NS)
		rec_xml.set("{%s}id" % NS, rec)
		rating_xml = ET.SubElement(rec_xml, "{%s}user-rating" % NS)
		if isinstance(rating, int):
			rating = "%d" % rating
		rating_xml.text = rating
	art_list = ET.SubElement(root, "{%s}artist-list" % NS)
	for art, rating in artist_ratings.items():
		art_xml = ET.SubElement(art_list, "{%s}artist" % NS)
		art_xml.set("{%s}id" % NS, art)
		rating_xml = ET.SubElement(rec_xml, "{%s}user-rating" % NS)
		if isinstance(rating, int):
			rating = "%d" % rating
		rating_xml.text = rating

	return ET.tostring(root, "utf-8")
