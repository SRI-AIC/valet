import re
import traceback

from .pane import Pane
from .state import StateStack
from valetrules.statement import \
    StatementParser, StatementRegion, BrokenRegion, CommentRegion, \
    InterpretableRegion, ImportRegion, TestExpressionRegion


class PatternPane(Pane):
    
    def __init__(self, parent, pattern_file, vrmanager):
        super().__init__(parent)
        self.state_stack.set_track_name(True)
        self.pattern_file = pattern_file
        self.vrm = vrmanager
        with open(pattern_file, "r") as fh:
            pattern_text = fh.read()
        self.insert(pattern_text)

        # Add a test tag to get the default background
        self.text_widget.tag_add("test tag", '1.0', '1.1')
        self.normal_background = self.text_widget.tag_cget('test tag', 'background')
        self.text_widget.tag_delete('test tag')

        self.names = []
        self.broken_count = 0
        self.reference_count = 0
        self.named_regions = {}
        self.name_to_tag = {}
        self.highlighted = set()

    def save(self):
        ptext = self.get_text()
        with open(self.pattern_file, "w") as fh:
            fh.write(ptext)

    def clear(self):
        for tname in self.names:
            self.text_widget.tag_config(tname, background=self.normal_background)

    def parse(self):
        # Remove all tags
        self.text_widget.tag_delete(*self.text_widget.tag_names())
        self.text_widget.tag_config('stuff', background='light gray')
        self.record_offsets()

        self.names = []
        self.named_regions = {}
        self.name_to_tag = {}
        self.tag_to_name = {}
        self.broken_count = 0
        self.reference_count = 0

        for region in self.get_pattern_regions():
            so, eo = self.region_offsets(region)
            if isinstance(region, BrokenRegion):
                self.set_broken_region(so, eo, region.brokenness)
            elif isinstance(region, CommentRegion):
                self.text_widget.tag_add('stuff', so, eo)
            elif isinstance(region, InterpretableRegion):  # TODO ExtractorRegion?
                self.set_interpretable_region(region)

    def invalidate_name(self, patname, msg):
        tagname = self.name_to_tag[patname]
        region = self.named_regions[tagname]
        so, eo = self.region_offsets(region)
        self.set_broken_region(so, eo, msg, clobber=tagname)
        self.set_current_name(None)
        del self.named_regions[tagname]

    def set_broken_region(self, so, eo, brokenness_msg, clobber=None):
        tagname = 'broken.%d' % self.broken_count
        self.broken_count += 1
        self.text_widget.tag_add(tagname, so, eo)
        self.text_widget.tag_config(tagname, background='LightPink')
        report = lambda e, msg=brokenness_msg: self.parent.message(msg)
        unreport = lambda e: self.parent.message("")
        self.text_widget.tag_bind(tagname, '<Enter>', report)
        self.text_widget.tag_bind(tagname, '<Leave>', unreport)
        if clobber is not None:
            self.text_widget.tag_remove(clobber, so, eo)
            self.text_widget.tag_remove(clobber.replace('name', 'expression'), so, eo)
            self.text_widget.tag_remove(clobber.replace('name', 'statement'), so, eo)
        self.update()

    def highlight(self, tname, exclusive=True):
        if exclusive:
            for tag in list(self.highlighted):
                self.unhighlight(tag)
        self.text_widget.tag_config(tname, underline=1)
        self.highlighted.add(tname)

    def unhighlight(self, tname):
        self.text_widget.tag_config(tname, underline=0)
        self.highlighted.discard(tname)

    def click_extractor_name(self, tname):
        self.state_stack.push()
        self.activate_tag(tname)

    def clear_active_tags(self):
        for tname in self.names:
            self.text_widget.tag_config(tname, background=self.normal_background)

    def activate_tag(self, tname):
        self.clear_active_tags()
        name = self.tag_to_name[tname]
        self.set_current_name(name)
        try:
            self.parent.display_pattern_matches(name)
            self.text_widget.tag_config(tname, background="light blue")
        except Exception as e:
            traceback.print_exc()
            stmt_tname = tname.replace('name', 'statement')
            so, eo = self.text_widget.tag_nextrange(stmt_tname, '1.0')
            self.set_broken_region(so, eo, str(e), clobber=tname)

    def restore_name(self, name):
        super().restore_name(name)
        if name is None:
            self.clear_active_tags()
        else:
            tname = self.name_to_tag[name]
            self.activate_tag(tname)

    def click_reference(self, pname):
        # TODO Built-ins throw exception here.
        tname = self.name_to_tag[pname]
        so, _ = self.text_widget.tag_nextrange(tname, '1.0')
        self.jump_to(so)
        self.click_extractor_name(tname)

    def jump_to(self, index):
        self.text_widget.see(index)
        self.state_stack.push()

    def set_interpretable_region(self, region):
        stmt_so, stmt_eo = self.region_offsets(region)
        name_region = region.spec_region
        name_so, name_eo = self.region_offsets(name_region)
        expr_region = region.expression_region
        expr_so, expr_eo = self.region_offsets(expr_region)
        tagname = 'name.%s' % name_so
        tagexpr = 'expression.%s' % name_so
        tagstmt = 'statement.%s' % name_so
        hl = lambda e, tn=tagname: self.highlight(tn)
        unhl = lambda e, tn=tagname: self.unhighlight(tn)
        clk = lambda e, tn=tagname: self.click_extractor_name(tn)
        self.text_widget.tag_add(tagname, name_so, name_eo)
        self.text_widget.tag_add(tagexpr, expr_so, expr_eo)
        self.text_widget.tag_add(tagstmt, stmt_so, stmt_eo)
        self.text_widget.tag_bind(tagname, '<Enter>', hl)
        self.text_widget.tag_bind(tagname, '<Leave>', unhl)
        if not isinstance(region, ImportRegion):
            # don't allow scan for match of import statement name;
            # doesn't make sense and causes exception
            self.text_widget.tag_bind(tagname, '<Button>', clk)
        self.names.append(tagname)
        self.named_regions[tagname] = region
        name = region.spec_region.source_string()
        self.name_to_tag[name] = tagname
        # TODO? This is not defined on all InterpretableRegions, hence 
        # compiler warning, but ones it's not defined on don't get here.
        namespace = region.get_namespace()
        if namespace is None:
            self.tag_to_name[tagname] = name
        else:
            self.tag_to_name[tagname] = "%s.%s" % (namespace, name)
        self.activate_references(region)

    def activate_references(self, region):
        if region.interpretation is None:
            return
        if not hasattr(region.interpretation, 'references'):
            return
        refs = region.interpretation.references()
        if len(refs) == 0:
            return
        expr_region = region.expression_region
        si, ei = self.region_offsets(expr_region)
        text = self.text_widget.get(si, ei)
        for m in re.finditer(r'\b\w+\b', text):
            word = m.group(0)
            if word in refs:
                so = expr_region.start_offset + m.start(0)
                wsi = self.offset_to_index(so)
                wei = self.offset_to_index(so + len(word))
                tagname = 'reference.%d' % self.reference_count
                hl = lambda e, tn=tagname: self.highlight(tn)
                unhl = lambda e, tn=tagname: self.unhighlight(tn)
                clk = lambda e, pname=word: self.click_reference(pname)
                self.reference_count += 1
                self.text_widget.tag_add(tagname, wsi, wei)
                self.text_widget.tag_bind(tagname, '<Enter>', hl)
                self.text_widget.tag_bind(tagname, '<Leave>', unhl)
                self.text_widget.tag_bind(tagname, '<Button>', clk)

    def get_pattern_regions(self):
        """
        Parse the pattern file and register the patterns with VRManager.
        Record the char offsets within the pattern file of each line.
        """
        # print(f"GUI pattern pane parsing pattern file {self.pattern_file}")
        self.vrm.forget()
        ptext = self.get_text()
        # Code here is similar to VRManager.parse_block.
        parser = StatementParser(ptext)
        regions = []
        region: StatementRegion
        for region in parser.regions():
            try:
                region.register(self.vrm)
                regions.append(region)
            except Exception as ex:
                traceback.print_exc()
                # Put this after the traceback so it's easier to spot.
                # It duplicates the last line of the traceback, but the
                # upper case makes it easier to spot, and we drop the
                # exception type, which is not usually helpful to
                # non-developers.
                # Plus if it's our own message -- and it usually should be
                # if it's not due to a code bug -- the message alone should
                # be sufficient.
                print("VRGUI PATTERN PARSE ERROR: %s" % ex)
                regions.append(BrokenRegion(region.text, region.start_offset, region.end_offset, str(ex)))
        return regions

    def get_requirements(self):
        return self.vrm.requirements()

    def get_test_names(self):
        regions = self.named_regions
        return [self.tag_to_name[name] for name in regions.keys() if isinstance(regions[name], TestExpressionRegion)]

