"""Local safety checks. Run without internet, AI or GitHub secrets."""
import unittest
from guard import apply_patches, is_auto_publish_safe, UnsafePatch, sync_engine

END="})(typeof window!=='undefined'?window:globalThis);"
HTML=f"<html><style>body{{color:red}}</style><script>/* LIFE Financial Studio\n(function(root){{}})({{}});\n{END}\n</script><p>TEST</p></html>"
ENGINE=f"/* LIFE Financial Studio\n(function(root){{}})({{}});\n{END}\n"

class TestGuard(unittest.TestCase):
    def setUp(self): self.old={'index.html':HTML,'engine.js':ENGINE}
    def test_auto_css_only(self):
        new=apply_patches(self.old,[{'file':'index.html','old':'color:red','new':'color:blue'}])
        self.assertTrue(is_auto_publish_safe(self.old,new))
    def test_css_external_network_is_manual(self):
        new=apply_patches(self.old,[{'file':'index.html','old':'color:red','new':'background:url(https://example.com)'}])
        self.assertFalse(is_auto_publish_safe(self.old,new))
    def test_financial_code_is_manual(self):
        new=apply_patches(self.old,[{'file':'engine.js','old':'(function(root){})','new':'(function(root){/* changed */})'}])
        self.assertFalse(is_auto_publish_safe(self.old,new))
        self.assertIn('/* changed */',new['index.html'])
    def test_no_workflow_edit(self):
        with self.assertRaises(UnsafePatch): apply_patches(self.old,[{'file':'.github/workflows/ai-dev.yml','old':'a','new':'b'}])
    def test_no_duplicate_search(self):
        with self.assertRaises(UnsafePatch): apply_patches(self.old,[{'file':'index.html','old':'<','new':'X'}])
    def test_no_engine_patch_in_html(self):
        with self.assertRaises(UnsafePatch): apply_patches(self.old,[{'file':'index.html','old':'(function(root){})','new':'evil'}])

if __name__=='__main__':unittest.main()
