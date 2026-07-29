/**
 * Trig Ops — Vendor Document Auto-Filer  (Google Apps Script)
 * ------------------------------------------------------------
 * Saves PDF / spreadsheet attachments from the Gmail "Orders" label into a
 * Drive folder ("Trig Ops - Vendor Docs"), then labels the thread so it is
 * never processed twice. The hourly Trig ops scan reads that folder, parses
 * each doc (SKU + side mark), auto-matches it to the customer order, and
 * attaches it to the order timeline.
 *
 * ONE-TIME INSTALL (≈2 min):
 *   1. Go to script.google.com  →  New project
 *   2. Delete the sample code, paste ALL of this in, Save
 *   3. Run  fileVendorDocs  once  →  approve the Google permission prompt
 *   4. Left rail ⏰ Triggers  →  Add Trigger:
 *        function: fileVendorDocs | event source: Time-driven |
 *        type: Minutes timer | every 15 minutes
 *   Done. It now runs itself.
 *
 * Share the "Trig Ops - Vendor Docs" folder with ryan@ / ami@ / justin@ so
 * they can open documents from the dashboard.
 */

const FOLDER_NAME = 'Trig Ops - Vendor Docs';
const SRC_LABEL   = 'Orders';       // existing Gmail label vendor mail lands under
const DONE_LABEL  = 'Ops/Filed';    // added after filing so we don't repeat

function fileVendorDocs() {
  const folder = getOrCreateFolder_(FOLDER_NAME);
  const done   = getOrCreateLabel_(DONE_LABEL);

  const threads = GmailApp.search(
    'label:"' + SRC_LABEL + '" has:attachment -label:"' + DONE_LABEL + '" newer_than:60d', 0, 50);

  threads.forEach(function (thread) {
    thread.getMessages().forEach(function (msg) {
      msg.getAttachments().forEach(function (att) {
        const type = att.getContentType() || '';
        const keep = type.indexOf('pdf') > -1 || type.indexOf('spreadsheet') > -1 ||
                     type.indexOf('excel') > -1 || type.indexOf('officedocument') > -1;
        if (!keep) return;

        const sender = String(msg.getFrom()).replace(/[<>@"]/g, ' ').trim().split(/\s+/)[0];
        const stamp  = Utilities.formatDate(msg.getDate(), 'America/New_York', 'yyyyMMdd');
        const name   = stamp + ' ' + sender + ' ' + att.getName();

        if (folder.getFilesByName(name).hasNext()) return;   // already saved
        folder.createFile(att.copyBlob()).setName(name)
              .setDescription('From: ' + msg.getFrom() + ' | Subject: ' + msg.getSubject());
      });
    });
    thread.addLabel(done);
  });
}

function getOrCreateFolder_(name) {
  const it = DriveApp.getFoldersByName(name);
  return it.hasNext() ? it.next() : DriveApp.createFolder(name);
}
function getOrCreateLabel_(name) {
  return GmailApp.getUserLabelByName(name) || GmailApp.createLabel(name);
}
