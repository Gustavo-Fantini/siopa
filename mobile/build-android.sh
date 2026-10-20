#!/usr/bin/env sh
set -eu
project_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
export GRADLE_USER_HOME="${GRADLE_USER_HOME:-$project_root/.tools/gradle-cache}"
export ANDROID_USER_HOME="${ANDROID_USER_HOME:-$project_root/.tools/android-user}"
sh "$project_root/mobile/android/gradlew" -p "$project_root/mobile/android" --no-daemon --console=plain "${1:-assembleDebug}"
