/**
 * MiLB Prospect Scanner — Google Sheets databank.
 *
 * Deploy this as a Web App:
 *   1. Extensions > Apps Script (in the Google Sheet you want as your databank).
 *   2. Paste this file in as Code.gs.
 *   3. Project Settings > Script Properties > add a property named SHARED_SECRET
 *      with a long random value. This is the secret the GitHub Action authenticates
 *      with — do NOT hardcode it in this file.
 *   4. Deploy > New deployment > type "Web app".
 *        - Execute as: Me
 *        - Who has access: Anyone
 *   5. Copy the deployment URL (ends in /exec). That's your APPS_SCRIPT_URL secret
 *      in GitHub. The SHARED_SECRET value from step 3 is your APPS_SCRIPT_SECRET.
 *
 * Sheet layout this creates automatically:
 *   - "Batter", "Pitcher", "Catcher" tabs — one row per player-season-team, upserted
 *     by (player_id, season, team_id). Header row is written from the first payload.
 *   - "_SyncState" tab — internal bookkeeping. One row per season, with a
 *     "complete" flag. Don't edit this by hand unless you want to force a re-pull
 *     of a given season (set complete to FALSE, or delete the row).
 */

const SYNC_STATE_SHEET = "_SyncState";
const KEY_FIELDS = ["player_id", "season", "team_id"];
const GAME_LOG_KEY_FIELDS = ["player_id", "season", "game_pk"];

function _keyFieldsFor(sheetName) {
  return sheetName.indexOf("GameLog") !== -1 ? GAME_LOG_KEY_FIELDS : KEY_FIELDS;
}

function _stateSheetName(kind) {
  return kind && kind !== "season" ? "_SyncState_" + kind : SYNC_STATE_SHEET;
}

function _secret() {
  return PropertiesService.getScriptProperties().getProperty("SHARED_SECRET");
}

function _checkSecret(provided) {
  const expected = _secret();
  if (!expected) {
    throw new Error("SHARED_SECRET is not configured in Script Properties.");
  }
  if (provided !== expected) {
    throw new Error("Invalid secret.");
  }
}

function _jsonOut(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function _getOrCreateSheet(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(name);
  if (!sheet) {
    sheet = ss.insertSheet(name);
  }
  return sheet;
}

function doGet(e) {
  try {
    const params = e.parameter || {};
    _checkSecret(params.secret);

    const action = params.action;
    if (action === "state") {
      return _jsonOut({ ok: true, completed_seasons: _getCompletedSeasons(params.kind || "season") });
    }
    if (action === "season_rows") {
      return _jsonOut({ ok: true, rows: _getSeasonLevelRows(params.sheet) });
    }
    return _jsonOut({ ok: false, error: "Unknown action: " + action });
  } catch (err) {
    return _jsonOut({ ok: false, error: String(err) });
  }
}

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);
    _checkSecret(body.secret);

    const action = body.action;
    if (action === "sync_rows") {
      const n = _upsertRows(body.sheet, body.rows || []);
      return _jsonOut({ ok: true, upserted: n });
    }
    if (action === "mark_complete") {
      _markSeasonComplete(body.season, body.kind || "season");
      return _jsonOut({ ok: true });
    }
    return _jsonOut({ ok: false, error: "Unknown action: " + action });
  } catch (err) {
    return _jsonOut({ ok: false, error: String(err) });
  }
}

/** Upsert `rows` (array of flat objects) into `sheetName`, keyed by KEY_FIELDS.
 * Creates the sheet + header row on first write. Returns rows written. */
function _upsertRows(sheetName, rows) {
  if (!rows || rows.length === 0) return 0;

  const sheet = _getOrCreateSheet(sheetName);
  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();

  let header;
  let existingIndex = {}; // key -> 1-based sheet row number

  if (lastRow === 0) {
    // Brand new sheet: header comes from the union-preserving order of the first row.
    header = Object.keys(rows[0]);
    sheet.getRange(1, 1, 1, header.length).setValues([header]);
  } else {
    header = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
    if (lastRow > 1) {
      const existingData = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
      const keyCols = KEY_FIELDS.map(function (f) { return header.indexOf(f); });
      for (let i = 0; i < existingData.length; i++) {
        const key = keyCols.map(function (c) { return existingData[i][c]; }).join("|");
        existingIndex[key] = i + 2; // +2: 1-based, plus header row
      }
    }
  }

  const keyColIdx = _keyFieldsFor(sheetName).map(function (f) { return header.indexOf(f); });
  const toAppend = [];

  rows.forEach(function (row) {
    const values = header.map(function (col) {
      const v = row[col];
      return v === undefined || v === null ? "" : v;
    });
    const key = keyColIdx.map(function (c) { return values[c]; }).join("|");

    if (existingIndex[key]) {
      sheet.getRange(existingIndex[key], 1, 1, header.length).setValues([values]);
    } else {
      toAppend.push(values);
    }
  });

  if (toAppend.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, toAppend.length, header.length)
      .setValues(toAppend);
  }

  return rows.length;
}

function _getCompletedSeasons(kind) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(_stateSheetName(kind));
  if (!sheet || sheet.getLastRow() < 2) return [];

  const data = sheet.getRange(2, 1, sheet.getLastRow() - 1, 2).getValues();
  return data
    .filter(function (row) { return row[1] === true; })
    .map(function (row) { return row[0]; });
}

/** Distinct (player_id, season, team_level) triples already on `sheetName` --
 * how the game-log pipeline finds targets across every season ever synced. */
function _getSeasonLevelRows(sheetName) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  if (!sheet || sheet.getLastRow() < 2) return [];

  const lastRow = sheet.getLastRow();
  const lastCol = sheet.getLastColumn();
  const header = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  const pIdx = header.indexOf("player_id");
  const sIdx = header.indexOf("season");
  const lIdx = header.indexOf("team_level");
  if (pIdx < 0 || sIdx < 0 || lIdx < 0) return [];

  const data = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
  const seen = {};
  const out = [];
  data.forEach(function (row) {
    const key = row[pIdx] + "|" + row[sIdx] + "|" + row[lIdx];
    if (!seen[key]) {
      seen[key] = true;
      out.push([row[pIdx], row[sIdx], row[lIdx]]);
    }
  });
  return out;
}

function _markSeasonComplete(season, kind) {
  const sheet = _getOrCreateSheet(_stateSheetName(kind));
  if (sheet.getLastRow() === 0) {
    sheet.getRange(1, 1, 1, 3).setValues([["season", "complete", "synced_at"]]);
  }

  const lastRow = sheet.getLastRow();
  let rowNum = null;
  if (lastRow > 1) {
    const seasons = sheet.getRange(2, 1, lastRow - 1, 1).getValues();
    for (let i = 0; i < seasons.length; i++) {
      if (seasons[i][0] === season) {
        rowNum = i + 2;
        break;
      }
    }
  }

  const values = [[season, true, new Date().toISOString()]];
  if (rowNum) {
    sheet.getRange(rowNum, 1, 1, 3).setValues(values);
  } else {
    sheet.getRange(sheet.getLastRow() + 1, 1, 1, 3).setValues(values);
  }
}
