import time
from test_backend import AccountPaymentTests
from backend.models import Site

class BackupTests(AccountPaymentTests):
 def test_backup_requires_restore_verification_for_healthy_state(self):
  owner=self.login('owner');base={'kind':'router_export','version':'ros-7','checksum':'a'*32,'encrypted':True,'storage_ref':'s3://private/backup-1'}
  self.assertEqual(self.client.post('/v1/backups',headers=owner,json={**base,'status':'healthy'}).status_code,422)
  result=self.client.post('/v1/backups',headers=owner,json={**base,'status':'healthy','restore_verified':True});self.assertEqual(result.status_code,201);self.assertTrue(result.json()['restore_verified'])
 def test_unencrypted_device_backup_is_rejected(self):
  owner=self.login('owner');body={'kind':'device_config','version':'1','checksum':'b'*32,'encrypted':False,'storage_ref':'local/test'}
  self.assertEqual(self.client.post('/v1/backups',headers=owner,json=body).status_code,422)
 def test_backup_inventory_is_tenant_scoped(self):
  owner=self.login('owner');body={'kind':'control_plane','version':'1','checksum':'c'*32,'encrypted':True,'storage_ref':'private/one'};self.assertEqual(self.client.post('/v1/backups',headers=owner,json=body).status_code,201)
  self.assertEqual(self.client.get('/v1/backups',headers=self.login('other')).json(),[]);self.assertEqual(self.client.get('/v1/backups',headers=self.login('guest')).status_code,403)
