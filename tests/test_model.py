# (c) Copyright 2017-2018 SUSE LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from contextlib import contextmanager
import copy
import os
from oslo_log import log as logging
import six
import testtools
import yaml

from ardana_service import model

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'test_data')
LOG = logging.getLogger(__name__)


@contextmanager
def log_level(level, name):
    # Enable modifying logging level in a context manager
    logger = logging.getLogger(name)
    # Get the effective level of the underlying logging object, and modify it
    old_level = logger.logger.getEffectiveLevel()
    logger.logger.setLevel(level)
    try:
        yield logger
    finally:
        logger.logger.setLevel(old_level)


class TestReadInvalidModels(testtools.TestCase):

    def test_read_model_missing_config(self):
        self.assertRaises(IOError, model.read_model, TEST_DATA_DIR)

    def test_read_invalid_yml(self):
        model_dir = os.path.join(TEST_DATA_DIR, 'invalid_yml')
        with log_level(logging.CRITICAL, "ardana_service.model"):
            self.assertRaises(yaml.YAMLError, model.read_model, model_dir)

    def test_read_invalid_dir(self):
        model_dir = os.path.join(TEST_DATA_DIR, 'doesnotexist')
        self.assertRaises(IOError, model.read_model, model_dir)


class TestReadModels(testtools.TestCase):

    def test_read_empty_section(self):
        model_dir = os.path.join(TEST_DATA_DIR, 'empty_section')
        model.read_model(model_dir)
        # No exceptions should be thrown


# Note that this class does not inherit from TestCase, but its descendants do
class TestWriteModels(object):

    def test_no_changes(self):
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        affected_files = [k for k, v in changes.items()
                          if v['status'] != model.IGNORED]
        self.assertEqual(0, len(affected_files))

    def test_add_servers(self):
        before_len = len(self.data['inputModel']['servers'])

        num_to_add = 5
        # grab last server and make extra copies of it
        server = self.data['inputModel']['servers'][-1:][0]
        for i in range(0, num_to_add):
            clone = copy.deepcopy(server)
            clone['id'] = 'server-%s' % i
            self.data['inputModel']['servers'].append(clone)

        changes = model.write_model(self.data, self.model_dir, dry_run=True)
        changed_files = [k for k, v in changes.items()
                         if v['status'] == model.CHANGED]

        self.assertEqual(1, len(changed_files))
        self.assertEqual(changed_files[0], "data/servers.yml")
        after_len = len(changes[changed_files[0]]['data']['servers'])
        self.assertEqual(before_len + num_to_add, after_len)

    def test_add_disk_models(self):
        num_to_add = 5
        # grab last disk model and make extra copies of it
        disk_model = self.data['inputModel']['disk-models'][-1:][0]
        for i in range(0, num_to_add):
            clone = copy.deepcopy(disk_model)
            clone['name'] = 'model-%s' % i
            self.data['inputModel']['disk-models'].append(clone)

        changes = model.write_model(self.data, self.model_dir, dry_run=True)
        added_files = [k for k, v in changes.items()
                       if v['status'] == model.ADDED]

        self.assertEqual(num_to_add, len(added_files))

    def test_add_to_uneven_split(self):
        # Manipulate the model to make it appear that the 3 disk-models are
        # distributed over just 2 files rather than 3.
        source = 'data/disks_compute.yml'
        dest = 'data/disks_controller_1TB.yml'
        model_name = 'COMPUTE-DISKS'

        # Move the model to one of the other file sections
        self.data['fileInfo']['fileSectionMap'].pop(source)

        for section in self.data['fileInfo']['fileSectionMap'][dest]:
            if isinstance(section, dict) and 'disk-models' in section:
                section['disk-models'].append(model_name)
                break

        self.data['fileInfo']['files'] = [
            f for f in self.data['fileInfo']['files'] if f != source]
        self.data['fileInfo']['sections']['disk-models'] = [
            f for f in self.data['fileInfo']['sections']['disk-models']
            if f != source]

        # Now add 2 disk-models
        self.data['inputModel']['disk-models'].append({"name": "FOO"})
        self.data['inputModel']['disk-models'].append({"name": "BAR"})

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        # There should be one file added with two disk models
        added = {k: v for k, v in changes.items()
                 if v['status'] == model.ADDED}

        # Remove the product for comparison to the added data
        new_data = next(six.itervalues(added))['data']

        # Should have 2 new disk models in the file (FOO and BAR)
        self.assertEqual(['FOO', 'BAR'], [
            f['name'] for f in new_data['disk-models']])

    def test_add_new_dict(self):
        added_dict = {'foo': {'bar': 'baz'}}
        self.data['inputModel'].update(added_dict)

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.ADDED, info['status'])

        # Remove the product for comparison to the added data
        new_data = next(six.itervalues(changed))['data']
        new_data.pop('product')

        self.assertEqual(added_dict, new_data)

    def test_add_new_list(self):
        added_list = {'foo': [{'name': 'bar'}, {'name': 'baz'}]}
        self.data['inputModel'].update(added_list)

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.ADDED, info['status'])

        # Remove the product for comparison to the added data
        new_data = next(six.itervalues(changed))['data']
        new_data.pop('product')

        self.assertEqual(added_list, new_data)

    def test_update_dict(self):
        # Modify the 'cloud' section, which is part of cloudConfig.yml
        self.data['inputModel']['cloud']['foo'] = 'bar'

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        self.assertIn('cloudConfig.yml', changed)

        info = next(six.itervalues(changed))
        self.assertEqual(model.CHANGED, info['status'])

    def test_delete_list(self):
        self.data['inputModel'].pop('control-planes')

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.DELETED, info['status'])

        self.assertIn('data/control_plane.yml', changed)


# Write tests with a model that originally contained two pass-through files
class TestWriteTwoPassthroughs(testtools.TestCase, TestWriteModels):

    @classmethod
    def setUpClass(cls):
        cls.model_dir = os.path.join(TEST_DATA_DIR, 'two_passthroughs')
        cls.test_data = model.read_model(cls.model_dir)

    def setUp(self):
        # Start each test with a fresh copy of the test data
        super(TestWriteTwoPassthroughs, self).setUp()
        self.data = copy.deepcopy(self.test_data)

    def test_update_pass_through(self):
        # Modify one of the values in data/neutron_passthrough.yml
        self.data['inputModel']['pass-through']['global']['esx_cloud2'] = False

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.CHANGED, info['status'])

        self.assertIn('data/neutron_passthrough.yml', changed)
        self.assertIn('esx_cloud2', info['data']['pass-through']['global'])

    def test_add_pass_through(self):

        # Modify one value in the existing pass-through.global dict
        self.data['inputModel']['pass-through']['global']['foo'] = 'bar'

        # And create a brand new section in pass-through
        self.data['inputModel']['pass-through']['newsection'] = 'baz'

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.ADDED, info['status'])

        filename = next(six.iterkeys(changed))

        # Should create some random filename that begins with pass-through
        self.assertTrue(filename.startswith('data/pass_through_'))

        self.assertIn('foo', info['data']['pass-through']['global'])
        self.assertIn('newsection', info['data']['pass-through'])

    def test_delete_pass_through(self):
        # Delete the only value in one of the pass-through sections
        self.data['inputModel']['pass-through']['global'].pop('esx_cloud2')

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.DELETED, info['status'])

        filename = next(six.iterkeys(changed))
        self.assertEqual('data/neutron_passthrough.yml', filename)


# Write tests with a model that originally contained one pass-through file
class TestWriteOnePassthrough(testtools.TestCase, TestWriteModels):

    @classmethod
    def setUpClass(cls):
        cls.model_dir = os.path.join(TEST_DATA_DIR, 'one_passthrough')
        cls.test_data = model.read_model(cls.model_dir)

    def setUp(self):
        super(TestWriteOnePassthrough, self).setUp()
        # Start each test with a fresh copy of the test data
        self.data = copy.deepcopy(self.test_data)

    def test_add_pass_through(self):

        # Modify one value in the existing pass-through.global dict
        self.data['inputModel']['pass-through']['global']['foo'] = 'bar'

        # And create a brand new section in pass-through
        self.data['inputModel']['pass-through']['newsection'] = 'baz'

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        # All pass_through contents should be written to the existing file
        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.CHANGED, info['status'])

        filename = next(six.iterkeys(changed))
        self.assertEqual('data/pass_through.yml', filename)

        self.assertIn('foo', info['data']['pass-through']['global'])
        self.assertIn('newsection', info['data']['pass-through'])

    def test_delete_pass_through(self):
        # Delete the only value in one of the pass-through sections
        self.data['inputModel'].pop('pass-through')

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.DELETED, info['status'])

        filename = next(six.iterkeys(changed))
        self.assertEqual('data/pass_through.yml', filename)


# Write tests with a model that originally contained no pass-through file
class TestWriteNoPassthrough(testtools.TestCase, TestWriteModels):

    @classmethod
    def setUpClass(cls):
        cls.model_dir = os.path.join(TEST_DATA_DIR, 'no_passthrough')
        cls.test_data = model.read_model(cls.model_dir)

    def setUp(self):
        super(TestWriteNoPassthrough, self).setUp()
        # Start each test with a fresh copy of the test data
        self.data = copy.deepcopy(self.test_data)

    def test_add_pass_through(self):

        # Add a passthrough section
        self.data['inputModel']['pass-through'] = {}
        self.data['inputModel']['pass-through']['global'] = {}
        self.data['inputModel']['pass-through']['global']['foo'] = 'bar'

        # Write the changes
        changes = model.write_model(self.data, self.model_dir, dry_run=True)

        changed = {k: v for k, v in changes.items()
                   if v['status'] != model.IGNORED}
        self.assertEqual(1, len(changed))

        info = next(six.itervalues(changed))
        self.assertEqual(model.ADDED, info['status'])

        filename = next(six.iterkeys(changed))

        # Should create some random filename that begins with pass-through
        self.assertTrue(filename.startswith('data/pass_through_'))

        self.assertIn('foo', info['data']['pass-through']['global'])
