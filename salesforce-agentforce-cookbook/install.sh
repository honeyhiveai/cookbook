#!/bin/bash
# Copy the poller, poller.env, and state file into /srv/agentforce and
# create the agentforce service user. Run from this directory after you
# have previewed and pinned one conversation.
set -eu

named=$(
  unset EXPORTED_FILE
  set -a
  # shellcheck disable=SC1091
  . ./poller.env
  set +a
  printf %s "${EXPORTED_FILE-}"
)
named=${named#"${named%%[![:space:]]*}"}
named=${named%"${named##*[![:space:]]}"}
exported_file=${named:-.agentforce-exported.json}
case "$exported_file" in
  /*) dest=$exported_file ;;
  *) dest=/srv/agentforce/$exported_file ;;
esac
skip_install=0
case "$exported_file" in
  *..*)
    printf '%s\n' "EXPORTED_FILE must not contain \"..\". Use a path under this directory, or an absolute path inside a directory dedicated to the poller." >&2
    skip_install=1
    ;;
esac
dest_dir=$(dirname "$dest")
if [ "$skip_install" -eq 0 ] && [ "$exported_file" = "$dest" ]; then
    dest_owner=
    if [ -d "$dest_dir" ] || sudo test -d "$dest_dir"; then
      dest_owner=$(sudo stat -c %U "$dest_dir" 2>/dev/null || printf '%s\n' "")
    fi
  if [ "$dest_owner" != agentforce ]; then
    case "$dest_dir" in
      /home/*|/root/*)
        printf '%s\n' "EXPORTED_FILE parent $dest_dir is inside a home directory. Point EXPORTED_FILE at a directory dedicated to the poller, such as /var/lib/agentforce/state.json." >&2
        skip_install=1
        ;;
    esac
    if [ "$skip_install" -eq 0 ]; then
      if [ "$dest_dir" = /root ] || { [ "$dest_dir" != /srv/agentforce ] && getent passwd | cut -d: -f6 | grep -qxF "$dest_dir"; }; then
        printf '%s\n' "EXPORTED_FILE parent $dest_dir is a login home directory. Point EXPORTED_FILE at a directory dedicated to the poller, such as /var/lib/agentforce/state.json." >&2
        skip_install=1
      else
        case "$dest_dir" in
          /|/etc|/opt|/srv|/tmp|/usr|/var|/var/lib|/var/tmp|/home)
            printf '%s\n' "EXPORTED_FILE parent $dest_dir is a shared directory. Point EXPORTED_FILE at a directory dedicated to the poller, such as /var/lib/agentforce/state.json." >&2
            skip_install=1
            ;;
        esac
      fi
    fi
    if [ "$skip_install" -eq 0 ] && sudo test -d "$dest_dir"; then
      if sudo test -z "$(sudo ls -A "$dest_dir" 2>/dev/null)"; then
        printf '%s\n' "EXPORTED_FILE parent $dest_dir exists, is empty, and is owned by ${dest_owner:-unknown}, not agentforce. If you pre-created it for the poller, run sudo chown agentforce $dest_dir and re-run this script." >&2
      else
        printf '%s\n' "EXPORTED_FILE parent $dest_dir exists, is not empty, and is owned by ${dest_owner:-unknown}, not agentforce. Point EXPORTED_FILE at a directory that does not exist yet, or that agentforce already owns." >&2
      fi
      skip_install=1
    fi
  fi
fi
if [ "$skip_install" -eq 0 ] && ! sudo test -f "$exported_file"; then
  if [ "$exported_file" != "$dest" ] && [ -n "$named" ] && [ -f .agentforce-exported.json ]; then
    printf '%s\n' "EXPORTED_FILE names $exported_file, which is missing. The pin wrote .agentforce-exported.json. Copy or rename it before you run this script." >&2
    skip_install=1
  elif [ "$exported_file" = "$dest" ] && [ -f .agentforce-exported.json ]; then
    printf '%s\n' "No state file at $dest, but .agentforce-exported.json is here. After this script finishes, run: sudo install -o agentforce -m 0644 .agentforce-exported.json $dest." >&2
  else
    printf '%s\n' "No state file at $exported_file. Correct only if you skipped the pin. After this script finishes, copy the file EXPORTED_FILE named at the time onto this host and sudo install -o agentforce -m 0644 that file $dest." >&2
  fi
fi
if [ "$skip_install" -ne 0 ]; then
  exit 1
fi

id -u agentforce >/dev/null 2>&1 || sudo useradd --system --home /srv/agentforce --shell /usr/sbin/nologin agentforce
sudo mkdir -p /srv/agentforce
sudo chmod 750 /srv/agentforce
sudo chown agentforce /srv/agentforce
for module in poll_agentforce.py config.py net.py otel_map.py policy.py salesforce_api.py state.py; do
  sudo install -o agentforce -m 0644 "$module" "/srv/agentforce/$module"
done
sudo install -o agentforce -m 0600 poller.env /srv/agentforce/poller.env
if [ "$exported_file" = "$dest" ]; then
  if sudo test -d "$dest_dir"; then
    if sudo test -f "$dest"; then
      sudo chown agentforce "$dest"
      sudo chmod 0644 "$dest"
    fi
  else
    sudo install -d -o agentforce -m 0750 "$dest_dir"
    if sudo test -f "$dest"; then
      sudo chown agentforce "$dest"
      sudo chmod 0644 "$dest"
    fi
  fi
elif ! sudo test -f "$exported_file"; then
  sudo install -d -o agentforce -m 0750 "$dest_dir"
else
  sudo install -d -o agentforce -m 0750 "$dest_dir"
  sudo install -o agentforce -m 0644 "$exported_file" "$dest"
fi
rm -f poller.env
case "$exported_file" in
  /*) ;;
  *) rm -f "$exported_file" ;;
esac

printf '%s\n' "Installed to /srv/agentforce. Copy agentforce-poller.service from README.md, then systemctl daemon-reload && systemctl enable --now agentforce-poller."
